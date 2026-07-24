import pathlib
fonts_path = pathlib.Path(__file__).parent.parent.parent.resolve() / "fonts"

# Layout and design specifications
TITLE_FONT_PATH = str(fonts_path / "Beleren-Bold.ttf")
DETAIL_FONT_PATH = str(fonts_path / "MPlantin.ttf")

# Unicode character codes for mana icons from mana font.
# Doesn't include hybrid mana symbols and phyrexian colored mana symbols
ICON_FONT_PATH = str(fonts_path / "mana.ttf")
ICON_CODES = {
    "{W}": u"\ue600",
    "{U}": u"\ue601",
    "{B}": u"\ue602",
    "{R}": u"\ue603",
    "{G}": u"\ue604",
    "{C}": u"\ue904",
    "{X}": u"\ue615",
    "{0}": u"\ue605",
    "{1}": u"\ue606",
    "{2}": u"\ue607",
    "{3}": u"\ue608",
    "{4}": u"\ue609",
    "{5}": u"\ue60a",
    "{6}": u"\ue60b",
    "{7}": u"\ue60c",
    "{8}": u"\ue60d",
    "{9}": u"\ue60e",
    "{10}": u"\ue60f",
    "{11}": u"\ue610",
    "{12}": u"\ue611",
    "{13}": u"\ue612",
    "{14}": u"\ue613",
    "{15}": u"\ue614",
    "{16}": u"\ue62a",
    "{17}": u"\ue62b",
    "{18}": u"\ue62c",
    "{19}": u"\ue62d",
    "{20}": u"\ue62e",
    "{E}": u"\ue907", # energy counter
    "{T}": u"\ue61a", # tap
    "{Q}": u"\ue61b", # untap
    "{H}": u"\ue618", # phyrexian mana
    "{S}": u"\ue619", # snow mana
}
