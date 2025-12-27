import load
import save


def Calculations():
    data = load.lastSave()
    gehalt = float(data["Balance"].replace(".", "").replace(",", ".").replace("€", ""))
    ausgaben = data["Expenses"]
    Schulden = data["Debts"]

    monthly_debts = [debt for debt in Schulden if debt["debt_monthly"] == "Yes"]
    non_monthly_debts = [debt for debt in Schulden if debt["debt_monthly"] == "No"]

    # Separate monthly and one-time expenses
    monthly_expenses = [exp for exp in ausgaben if exp.get("is_monthly")]
    onetime_expenses = [exp for exp in ausgaben if not exp.get("is_monthly")]

    total_monthly_expenses = sum(float(expense["amount"]) for expense in monthly_expenses)
    total_onetime_expenses = sum(float(expense["amount"]) for expense in onetime_expenses)
    total_expenses = total_monthly_expenses + total_onetime_expenses

    total_one_time_debt = sum(int(debt["amount"]) for debt in non_monthly_debts)
    total_monthly_debt = sum(int(debt["amount"]) / int(debt["length"]) for debt in monthly_debts)
    total_debt = total_one_time_debt + total_monthly_debt

    remaining_income = gehalt - total_expenses - total_debt

    return total_expenses, total_monthly_expenses, total_onetime_expenses, total_one_time_debt, total_monthly_debt, total_debt, remaining_income



def get_debts():
    """Load and return all debts from save.json"""
    data = load.lastSave()
    return data.get("Debts", [])

def add_debt(name, amount, start_date, is_monthly, length=0):
    """Add a new debt to save.json"""
    import save as save_module
    data = load.lastSave()
    Schulden = data.get("Debts", [])

    new_debt = {
        "name": name,
        "amount": amount,
        "start_date": start_date,
        "debt_monthly": "Yes" if is_monthly else "No",
        "length": str(length)
    }

    Schulden.append(new_debt)

    # Save updated data using save.py
    save_module.save_data(data["Balance"], data["lastPayCheck"], data["Expenses"], Schulden)

def remove_debt(debt_name):
    """Remove a debt from save.json by name"""
    import save as save_module
    data = load.lastSave()
    Schulden = data.get("Debts", [])

    # Remove debt with matching name
    Schulden = [d for d in Schulden if d['name'] != debt_name]

    # Save updated data using save.py
    save_module.save_data(data["Balance"], data["lastPayCheck"], data["Expenses"], Schulden)


def get_expenses():
    """Get all expenses from save.json"""
    data = load.lastSave()
    return data.get("Expenses", [])

def add_expense(name, amount, is_monthly=False, start_date=None):
    """Add a new expense to save.json"""
    data = load.lastSave()

    expense = {
        "name": name,
        "amount": amount,
        "is_monthly": is_monthly
    }

    if is_monthly and start_date:
        expense["start_date"] = start_date
        expense["cancel_date"] = None

    data["Expenses"].append(expense)
    save.save_data(data["Balance"], data["lastPayCheck"], data["Expenses"], data["Debts"])

def cancel_monthly_expense(name, cancel_date, immediate=True):
    """Cancel a monthly expense"""
    data = load.lastSave()

    for expense in data["Expenses"]:
        if expense["name"] == name and expense.get("is_monthly"):
            expense["cancel_date"] = cancel_date
            expense["immediate_cancel"] = immediate
            break

    save.save_data(data["Balance"], data["lastPayCheck"], data["Expenses"], data["Debts"])

def remove_expense(expense_name):
    #Remove an expense from save.json by name"
    import save as save_module
    data = load.lastSave()
    ausgaben = data.get("Expenses", [])

    # Remove expense with matching name
    ausgaben = [e for e in ausgaben if e['name'] != expense_name]

    # Save updated data using save.py
    save_module.save_data(data["Balance"], data["lastPayCheck"], ausgaben, data["Debts"])
