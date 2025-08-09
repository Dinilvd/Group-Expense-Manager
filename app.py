from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, flash
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "splitmoney"  # Use a strong random key

def init_db():
    with sqlite3.connect("db/database.db") as conn:
        with open("schema.sql") as f:
            conn.executescript(f.read())

if not os.path.exists("db/database.db"):
    init_db()

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        conn = sqlite3.connect("db/database.db")
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, password))
            conn.commit()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return "User already exists!"
        finally:
            conn.close()

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("db/database.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            return redirect(url_for("group"))
        else:
            return "Invalid credentials!"

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/group", methods=["GET", "POST"])
def group():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("db/database.db")
    cur = conn.cursor()

    cur.execute("SELECT id FROM groups WHERE user_id = ?", (session["user_id"],))
    group = cur.fetchone()

    if not group:
        cur.execute(
            "INSERT INTO groups (user_id, name) VALUES (?, ?)",
            (session["user_id"], session["user_name"] + "'s Group")
        )
        conn.commit()
        group_id = cur.lastrowid
    else:
        group_id = group[0]

    if request.method == "POST":
        name = request.form["name"].strip()
        cur.execute(
            "SELECT 1 FROM people WHERE group_id = ? AND LOWER(name) = LOWER(?)",
            (group_id, name)
        )
        exists = cur.fetchone()

        if exists:
            flash(f"'{name}' already exists in your group.")
        else:
            cur.execute("INSERT INTO people (group_id, name) VALUES (?, ?)", (group_id, name))
            conn.commit()
            flash(f"'{name}' added to the group.")

    cur.execute("SELECT id, name FROM people WHERE group_id = ?", (group_id,))
    people = cur.fetchall()

    conn.close()
    return render_template("group.html", people=people, group_id=group_id)

@app.route("/add", methods=["GET", "POST"])
def add_expense():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        amount = float(request.form["amount"])
        description = request.form["description"]
        date = request.form["date"]

        user_id = session["user_id"]

        conn = sqlite3.connect("db/database.db")
        cur = conn.cursor()

        cur.execute("INSERT INTO expenses (payer_id, amount, description, date) VALUES (?, ?, ?, ?)",
                    (user_id, amount, description, date))
        expense_id = cur.lastrowid

        cur.execute("INSERT INTO splits (expense_id, user_id, share) VALUES (?, ?, ?)",
                    (expense_id, user_id, amount))

        conn.commit()
        conn.close()

        return redirect(url_for("group"))

    return render_template("group.html")

@app.route("/group/<int:group_id>/add-expense", methods=["GET", "POST"])
def add_expense_in_group(group_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("db/database.db")
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM people WHERE group_id = ?", (group_id,))
    people = cur.fetchall()

    if request.method == "POST":
        payer_id = request.form["payer_id"]
        amount = float(request.form["amount"])
        category = request.form["category"]
        date = request.form["date"]
        split_type = request.form["split_type"]

        cur.execute("INSERT INTO expenses (payer_id, amount, description, date) VALUES (?, ?, ?, ?)",
                    (payer_id, amount, category, date))
        expense_id = cur.lastrowid

        if split_type == "equal":
            share = round(amount / len(people), 2)
            for person in people:
                cur.execute("INSERT INTO splits (expense_id, user_id, share) VALUES (?, ?, ?)",
                            (expense_id, person[0], share))
        else:
            total_shared = 0.0
            shares = []
            for person in people:
                share = float(request.form.get(f"share_{person[0]}", 0))
                shares.append((person[0], share))
                total_shared += share

            if round(total_shared, 2) != round(amount, 2):
                conn.rollback()
                flash(f"Total of shares ({total_shared}) does not match amount ({amount}).", "error")
                return redirect(request.url)

            for person_id, share in shares:
                cur.execute("INSERT INTO splits (expense_id, user_id, share) VALUES (?, ?, ?)",
                            (expense_id, person_id, share))

        conn.commit()
        conn.close()
        return redirect(request.url)

    cur.execute("""
        SELECT expenses.amount, expenses.description, expenses.date, people.name 
        FROM expenses 
        JOIN people ON expenses.payer_id = people.id 
        WHERE people.group_id = ?
        ORDER BY expenses.date DESC
    """, (group_id,))
    expenses = cur.fetchall()

    conn.close()
    return render_template("add_expense_group.html", people=people, group_id=group_id, expenses=expenses)

@app.route("/delete_person/<int:person_id>", methods=["POST"])
def delete_person(person_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("db/database.db")
    cur = conn.cursor()

    cur.execute("SELECT id FROM groups WHERE user_id = ?", (session["user_id"],))
    group = cur.fetchone()
    if not group:
        flash("Group not found.")
        conn.close()
        return redirect(url_for("group"))
    group_id = group[0]

    cur.execute("SELECT group_id, name FROM people WHERE id = ?", (person_id,))
    person = cur.fetchone()
    if not person or person[0] != group_id:
        flash("Cannot delete: This person does not belong to your group.")
        conn.close()
        return redirect(url_for("group"))
    person_name = person[1]

    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE payer_id = ?", (person_id,))
    paid = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(share), 0) FROM splits WHERE user_id = ?", (person_id,))
    owed = cur.fetchone()[0]

    cur.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN from_user_id = ? THEN amount ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN to_user_id = ? THEN amount ELSE 0 END), 0)
        FROM settlements
    """, (person_id, person_id))
    settled_sent, settled_received = cur.fetchone()

    net = round((paid + settled_sent) - (owed + settled_received), 2)

    print(f"Delete person_id: {person_id}, Name: {person_name}, Paid: {paid}, Owed: {owed}, Settled Sent: {settled_sent}, Settled Received: {settled_received}, Net: {net}")

    try:
        if abs(net) < 0.01:
            cur.execute("DELETE FROM people WHERE id = ?", (person_id,))
            conn.commit()
            flash(f"✅ Person '{person_name}' deleted successfully.")
        else:
            cur.execute("DELETE FROM expenses WHERE payer_id = ?", (person_id,))
            cur.execute("DELETE FROM splits WHERE user_id = ?", (person_id,))
            cur.execute("DELETE FROM settlements WHERE from_user_id = ? OR to_user_id = ?", (person_id, person_id))
            cur.execute("DELETE FROM people WHERE id = ?", (person_id,))
            conn.commit()
            flash(f"✅ Person '{person_name}' and their related records deleted successfully. Note: Their balance of ₹{net} was cleared.")
    except sqlite3.Error as e:
        conn.rollback()
        flash(f"❌ Error deleting person: {str(e)}")
        print(f"Database error: {str(e)}")
    finally:
        conn.close()

    return redirect(url_for("group"))

@app.route("/balances")
def balances():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("db/database.db")
    cur = conn.cursor()

    # Get the user's group ID
    cur.execute("SELECT id FROM groups WHERE user_id = ?", (session["user_id"],))
    group = cur.fetchone()
    if not group:
        flash("Group not found.")
        conn.close()
        return render_template("balances.html", balances=[])
    group_id = group[0]

    # Get people in the user's group
    cur.execute("SELECT id, name FROM people WHERE group_id = ?", (group_id,))
    users = cur.fetchall()
    user_map = {user[0]: user[1] for user in users}

    # Initialize balances
    balances = {uid: 0 for uid in user_map}

    # Add paid amounts for expenses in the group
    cur.execute("""
        SELECT e.payer_id, e.amount 
        FROM expenses e
        JOIN people p ON e.payer_id = p.id
        WHERE p.group_id = ?
    """, (group_id,))
    for payer_id, amount in cur.fetchall():
        if payer_id in balances:
            balances[payer_id] += amount

    # Subtract owed shares for splits in the group
    cur.execute("""
        SELECT s.user_id, s.share 
        FROM splits s
        JOIN expenses e ON s.expense_id = e.id
        JOIN people p ON e.payer_id = p.id
        WHERE p.group_id = ?
    """, (group_id,))
    for user_id, share in cur.fetchall():
        if user_id in balances:
            balances[user_id] -= share

    # Apply settlements within the group
    cur.execute("""
        SELECT s.from_user_id, s.to_user_id, s.amount 
        FROM settlements s
        JOIN people p1 ON s.from_user_id = p1.id
        JOIN people p2 ON s.to_user_id = p2.id
        WHERE p1.group_id = ? AND p2.group_id = ?
    """, (group_id, group_id))
    for from_id, to_id, amt in cur.fetchall():
        if from_id in balances:
            balances[from_id] += amt
        if to_id in balances:
            balances[to_id] -= amt

    # Calculate creditors and debtors
    creditors = [(uid, amt) for uid, amt in balances.items() if amt > 0.009]
    debtors = [(uid, -amt) for uid, amt in balances.items() if amt < -0.009]

    settlements = []

    while creditors and debtors:
        creditor_id, credit = creditors.pop(0)
        debtor_id, debt = debtors.pop(0)

        settled_amount = round(min(credit, debt), 2)
        debtor_name = user_map[debtor_id]
        creditor_name = user_map[creditor_id]

        if (
            creditor_id != debtor_id
            and debtor_name != creditor_name
            and settled_amount > 0.009
        ):
            settlements.append((debtor_name, creditor_name, settled_amount))

        if credit > debt:
            creditors.insert(0, (creditor_id, credit - debt))
        elif debt > credit:
            debtors.insert(0, (debtor_id, debt - credit))

    conn.close()
    return render_template("balances.html", balances=settlements)

@app.route("/settle_up")
def settle_up():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("db/database.db")
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM people")
    people = cur.fetchall()
    conn.close()

    return render_template("settle_up.html", people=people)

@app.route("/settle_up", methods=["POST"])
def settle_up_post():
    from_id = int(request.form["from_id"])
    to_id = int(request.form["to_id"])
    amount = float(request.form["amount"])
    date = request.form.get("date") or datetime.now().strftime("%Y-%m-%d")

    if from_id == to_id or amount <= 0:
        return redirect(url_for("balances"))

    conn = sqlite3.connect("db/database.db")
    cur = conn.cursor()

    cur.execute("INSERT INTO settlements (from_user_id, to_user_id, amount, date) VALUES (?, ?, ?, ?)",
                (from_id, to_id, amount, date))
    conn.commit()
    conn.close()

    return redirect(url_for("balances"))

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)