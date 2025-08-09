DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS groups;
DROP TABLE IF EXISTS people;
DROP TABLE IF EXISTS expenses;
DROP TABLE IF EXISTS splits;
DROP TABLE IF EXISTS settlements;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
);

CREATE TABLE groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER,
    name TEXT NOT NULL,
    FOREIGN KEY (group_id) REFERENCES groups(id)
);

CREATE TABLE expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payer_id INTEGER, -- now linked to people.id
    amount REAL NOT NULL,
    description TEXT,
    date TEXT,
    FOREIGN KEY (payer_id) REFERENCES people(id)
);

CREATE TABLE splits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER,
    user_id INTEGER, -- now linked to people.id
    share REAL,
    FOREIGN KEY (expense_id) REFERENCES expenses(id),
    FOREIGN KEY (user_id) REFERENCES people(id)
);

CREATE TABLE settlements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id INTEGER, -- now linked to people.id
    to_user_id INTEGER,
    amount REAL,
    date TEXT,
    FOREIGN KEY (from_user_id) REFERENCES people(id),
    FOREIGN KEY (to_user_id) REFERENCES people(id)
);
