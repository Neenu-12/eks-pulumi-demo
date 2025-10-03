import pulumi
import pulumi_aws as aws
import pulumi_eks as eks

# -----------------------------
# 1. VPC & Networking
# -----------------------------
vpc = aws.ec2.Vpc("login-vpc",
    cidr_block="10.0.0.0/16",
    tags={"Name": "login-vpc"}
)

# Public Subnets (optional for bastion/ALB)
public_subnet1 = aws.ec2.Subnet("public-subnet-1",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    availability_zone="ap-south-1a",
    map_public_ip_on_launch=True,
    tags={"Name": "public-subnet-1"}
)

public_subnet2 = aws.ec2.Subnet("public-subnet-2",
    vpc_id=vpc.id,
    cidr_block="10.0.2.0/24",
    availability_zone="ap-south-1b",
    map_public_ip_on_launch=True,
    tags={"Name": "public-subnet-2"}
)

# Private Subnets (EKS workloads run here)
private_subnet1 = aws.ec2.Subnet("private-subnet-1",
    vpc_id=vpc.id,
    cidr_block="10.0.3.0/24",
    availability_zone="ap-south-1a",
    tags={"Name": "private-subnet-1"}
)

private_subnet2 = aws.ec2.Subnet("private-subnet-2",
    vpc_id=vpc.id,
    cidr_block="10.0.4.0/24",
    availability_zone="ap-south-1b",
    tags={"Name": "private-subnet-2"}
)

# Security group for RDS allowing access from EKS pods
eks_sg = aws.ec2.SecurityGroup("eks-sg",
    vpc_id=vpc.id,
    description="Allow EKS pods to talk to RDS",
    ingress=[aws.ec2.SecurityGroupIngressArgs(
        protocol="tcp",
        from_port=5432,
        to_port=5432,
        cidr_blocks=["10.0.0.0/16"]
    )],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        protocol="-1",
        from_port=0,
        to_port=0,
        cidr_blocks=["0.0.0.0/0"]
    )]
)

# -----------------------------
# 2. RDS PostgreSQL
# -----------------------------
db = aws.rds.Instance("login-db",
    engine="postgres",
    instance_class="db.t3.micro",
    allocated_storage=20,
    db_name="loginapp",
    username="appuser",
    password="PulumiDemo123!",
    skip_final_snapshot=True,
    publicly_accessible=False,
    vpc_security_group_ids=[eks_sg.id],
    db_subnet_group_name=aws.rds.SubnetGroup("db-subnet-group",
        subnet_ids=[private_subnet1.id, private_subnet2.id],
        tags={"Name": "db-subnet-group"}).id
)

pulumi.export("db_endpoint", db.endpoint)
pulumi.export("db_name", db.db_name)

# -----------------------------
# 3. EKS Cluster (Fargate on private subnets)
# -----------------------------
cluster = eks.Cluster(
    "login-eks-cluster",
    vpc_id=vpc.id,
    subnet_ids=[private_subnet1.id, private_subnet2.id],  # only private subnets
    instance_type="t3.medium",
    desired_capacity=1,
    min_size=1,
    max_size=2,
    fargate=True,
)

# ----------------------------
# 4. Fargate Pod Execution Role
# ----------------------------
fargate_role = aws.iam.Role(
    "eksFargatePodExecutionRole",
    assume_role_policy="""{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "eks-fargate-pods.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }"""
)

aws.iam.RolePolicyAttachment(
    "eksFargatePodExecutionRoleAttachment",
    role=fargate_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEKSFargatePodExecutionRolePolicy"
)

# Fargate profile for default + kube-system (CoreDNS)
fargate_profile = aws.eks.FargateProfile(
    "fargate-profile",
    cluster_name=cluster.core.cluster.name,
    pod_execution_role_arn=fargate_role.arn,
    selectors=[
        {"namespace": "default"},
        {"namespace": "kube-system", "labels": {"k8s-app": "kube-dns"}},
    ],
    subnet_ids=[private_subnet1.id, private_subnet2.id],
    opts=pulumi.ResourceOptions(depends_on=[fargate_role])
)

pulumi.export("kubeconfig", cluster.kubeconfig)
pulumi.export("eks_cluster_name", cluster.eks_cluster.name)

