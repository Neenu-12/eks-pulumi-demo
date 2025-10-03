from flask import Flask, request, render_template_string
import hvac

app = Flask(__name__)

client = hvac.Client(url='http://<VAULT-IP>:8200', token='root')
creds = client.secrets.kv.v2.read_secret_version(path='db')['data']['data']

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == creds["username"] and request.form["password"] == creds["password"]:
            return "Welcome, authenticated user!"
        return "Invalid credentials"
    return render_template_string('''
        <form method="POST">
            Username: <input name="username"><br>
            Password: <input name="password" type="password"><br>
            <input type="submit" value="Login">
        </form>
    ''')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

