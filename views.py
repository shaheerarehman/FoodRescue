CSS = '''body{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 20px}nav a{margin-right:16px}.card{border:1px solid #ccc;padding:16px;margin:12px 0;border-radius:8px}.status{font-weight:bold}.actions{display:flex;gap:8px;align-items:center}.actions form{margin:0}input,textarea{display:block;width:100%;padding:8px;margin:6px 0 14px;box-sizing:border-box}button{padding:8px 14px}small{color:#555}'''


def page(title, body):
    return f'''<!doctype html><html><head><title>{title}</title><style>{CSS}</style></head><body><nav><a href="/">FoodRescue</a><a href="/donations/new">Donate</a><a href="/donations">Available Donations</a><a href="/donations/manage">Manage Donations</a><a href="/docs">API Docs</a></nav><hr>{body}</body></html>'''
