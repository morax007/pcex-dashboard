import sqlite3

def update_users_table():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Try adding new columns (ignore if they already exist)
    try:
        c.execute("ALTER TABLE users ADD COLUMN trial_start TEXT")
    except Exception as e:
        print("trial_start already exists or failed:", e)

    try:
        c.execute("ALTER TABLE users ADD COLUMN is_subscribed INTEGER DEFAULT 0")
    except Exception as e:
        print("is_subscribed already exists or failed:", e)

    try:
        c.execute("ALTER TABLE users ADD COLUMN plan TEXT")
    except Exception as e:
        print("plan already exists or failed:", e)

    try:
        c.execute("ALTER TABLE users ADD COLUMN subscription_expiry TEXT")
    except Exception as e:
        print("subscription_expiry already exists or failed:", e)

    try:
        c.execute("ALTER TABLE users ADD COLUMN pcex_username TEXT")
    except Exception as e:
        print("pcex_username already exists or failed:", e)

    try:
        c.execute("ALTER TABLE users ADD COLUMN pcex_password TEXT")
    except Exception as e:
        print("pcex_password already exists or failed:", e)

    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    update_users_table()
