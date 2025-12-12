import markdown
import os

# Reading MD
md_file = "PPT설명.md"
html_file = "PPT설명.html"

with open(md_file, "r", encoding="utf-8") as f:
    text = f.read()

# Converting to HTML
html_content = markdown.markdown(text, extensions=['tables', 'fenced_code'])

# Adding meaningful CSS
html_template = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>프로젝트 개선 상세 내역</title>
    <style>
        body {{
            font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px;
        }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 10px; }}
        h2 {{ margin-top: 40px; border-bottom: 1px solid #ddd; padding-bottom: 5px; color: #0056b3; }}
        h3 {{ margin-top: 30px; color: #444; }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
            font-weight: bold;
        }}
        code {{
            background-color: #f8f8f8;
            padding: 2px 5px;
            border-radius: 3px;
            font-family: Consolas, monospace;
        }}
        blockquote {{
            border-left: 4px solid #0056b3;
            margin: 0;
            padding-left: 15px;
            color: #555;
            background-color: #f9f9f9;
            padding: 10px;
        }}
        strong {{ color: #d63384; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
"""

with open(html_file, "w", encoding="utf-8") as f:
    f.write(html_template)

print(f"Successfully created {html_file}")
