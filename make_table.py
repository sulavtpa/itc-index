"""
this file generates table with course code, title and credit hour
generates in .webp format
webp was chosen as it is easily shareable and takes comparatively less space than png or jpg

Usage:
    py make_table.py                          makes ALL tables
    py make_table.py "Civil Engineering"      all semesters of civil
    py make_table.py "Civil Engineering" 1    only civil semester 1

Images are saved like: courses/computer/1st-sem-comp.webp

make sure there is pillow installed, if not run:

py -m pip install pillow

the file is formatted with extension named Ruff
"""

import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_SIZE = 60
PADDING_X = 42
ROW_HEIGHT = 135
MARGIN = 45
LINE_WIDTH = 3
HEADER = ["SN", "COURSE CODE", "Title", "CR (Credit Hour)"]
CENTERED_COLUMNS = [0, 3]
FOLDER_NAMES = {
    "bit": "bit",
    "arch": "arch",
    "civil": "civil",
    "comp": "computer",
    "bca": "bca-it",
    "eca": "elx",
}
SEMESTER_WORDS = {
    1: "1st",
    2: "2nd",
    3: "3rd",
    4: "4th",
    5: "5th",
    6: "6th",
    7: "7th",
    8: "8th",
    9: "9th",
    10: "10th",
}
HERE = os.path.dirname(os.path.abspath(__file__))


def read_course_file():
    path = os.path.join(HERE, "course.json")
    file = open(path, "r", encoding="utf-8")
    data = json.load(file)
    file.close()
    return data["departments"]


def find_department(departments, typed_text):
    typed_text = typed_text.lower().strip()
    for department in departments:
        if typed_text == department["short"].lower():
            return department
        if typed_text in department["name"].lower():
            return department
    return None


def draw_table(courses):
    font_path = os.path.join(HERE, "assets", "OpenSans.ttf")
    regular_font = ImageFont.truetype(font_path, FONT_SIZE)
    regular_font.set_variation_by_name("Regular")
    bold_font = ImageFont.truetype(font_path, FONT_SIZE)
    bold_font.set_variation_by_name("Bold")
    rows = [HEADER]
    for course in courses:
        rows.append(
            [
                str(course["sn"]),
                course["code"],
                course["title"],
                str(course["cr"]),
            ]
        )
    measure_image = Image.new("RGB", (10, 10), "white")
    measure = ImageDraw.Draw(measure_image)
    column_widths = [0, 0, 0, 0]
    for row_number in range(len(rows)):
        font = bold_font if row_number == 0 else regular_font
        for column in range(4):
            width = measure.textlength(rows[row_number][column], font=font)
            width = width + 2 * PADDING_X
            if width > column_widths[column]:
                column_widths[column] = width

    column_lefts = []
    x = MARGIN
    for column in range(4):
        column_lefts.append(x)
        x = x + column_widths[column]
    table_right = x

    table_top = MARGIN
    table_bottom = MARGIN + ROW_HEIGHT * len(rows)

    image = Image.new(
        "RGB",
        (int(table_right + MARGIN), int(table_bottom + MARGIN)),
        "white",
    )
    draw = ImageDraw.Draw(image)

    extra = LINE_WIDTH // 2

    for line_number in range(len(rows) + 1):
        y = table_top + line_number * ROW_HEIGHT
        draw.line(
            [(MARGIN - extra, y), (table_right + extra, y)],
            fill="black",
            width=LINE_WIDTH,
        )

    for column in range(4):
        x = column_lefts[column]
        draw.line(
            [(x, table_top - extra), (x, table_bottom + extra)],
            fill="black",
            width=LINE_WIDTH,
        )
    draw.line(
        [(table_right, table_top - extra), (table_right, table_bottom + extra)],
        fill="black",
        width=LINE_WIDTH,
    )

    for row_number in range(len(rows)):
        font = bold_font if row_number == 0 else regular_font
        middle_y = table_top + row_number * ROW_HEIGHT + ROW_HEIGHT / 2

        for column in range(4):
            text = rows[row_number][column]
            if column in CENTERED_COLUMNS:
                text_x = column_lefts[column] + column_widths[column] / 2
                anchor = "mm"
            else:
                text_x = column_lefts[column] + PADDING_X
                anchor = "lm"
            draw.text((text_x, middle_y), text, font=font, fill="black", anchor=anchor)

    return image


def make_one_table(department, semester):
    short_name = department["short"]

    if short_name not in FOLDER_NAMES:
        print("  Skipped: no folder name set for '" + short_name + "' in FOLDER_NAMES")
        return

    folder_name = FOLDER_NAMES[short_name]
    word = SEMESTER_WORDS[int(semester)]
    file_name = word + "-sem-" + short_name + ".webp"
    courses = department["semesters"][semester]

    folder_path = os.path.join(HERE, "courses", folder_name)
    file_path = os.path.join(folder_path, file_name)

    try:
        os.makedirs(folder_path, exist_ok=True)
        image = draw_table(courses)
        image.save(file_path, "WEBP", lossless=True)
        print("  Saved: courses/" + folder_name + "/" + file_name)
    except FileNotFoundError:
        print("  ERROR: could not find assets/OpenSans.ttf (check the font file name)")
    except KeyError as error:
        print("  ERROR: a course is missing this field in course.json: " + str(error))
    except Exception as error:
        print("  ERROR while making " + folder_name + " semester " + str(semester))
        print("  " + str(error))


def main():
    try:
        departments = read_course_file()
    except FileNotFoundError:
        print(
            "ERROR: course.json not found. Put it in the same folder as make_table.py"
        )
        return
    except json.JSONDecodeError as error:
        print("ERROR: course.json has a typo (missing comma or bracket?)")
        print(error)
        return

    arguments = sys.argv[1:]

    if len(arguments) == 0:
        for department in departments:
            print(department["name"])
            for semester in department["semesters"]:
                make_one_table(department, semester)
        return

    department = find_department(departments, arguments[0])
    if department is None:
        print(
            "ERROR: no department found for '" + arguments[0] + "'. Try one of these:"
        )
        for item in departments:
            print("  " + item["name"] + "   (or: " + item["short"] + ")")
        return

    print(department["name"])

    if len(arguments) == 1:
        for semester in department["semesters"]:
            make_one_table(department, semester)
        return

    semester = arguments[1]
    if semester not in department["semesters"]:
        print("ERROR: semester '" + semester + "' not found. Available:")
        for number in department["semesters"]:
            print("  " + number)
        return

    make_one_table(department, semester)


main()
