import re

def main():
    with open('static/index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    style_match = re.search(r'<style>(.*?)</style>', content, re.DOTALL)
    if style_match:
        with open('static/style.css', 'w', encoding='utf-8') as f:
            f.write(style_match.group(1).strip())
        content = content.replace(style_match.group(0), '<link rel="stylesheet" href="/static/style.css">')

    script_match = re.search(r'<script>(.*?)</script>', content, re.DOTALL)
    if script_match:
        with open('static/app.js', 'w', encoding='utf-8') as f:
            f.write(script_match.group(1).strip())
        content = content.replace(script_match.group(0), '<script src="/static/app.js"></script>')

    with open('static/index.html', 'w', encoding='utf-8') as f:
        f.write(content)

    print("Split complete.")

if __name__ == '__main__':
    main()
