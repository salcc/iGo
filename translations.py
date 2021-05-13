import os

strings = {}
translations = {}


def build_translation_dictionaries():
    with open('translations/en.txt') as en:
        for line_num, message in enumerate(en.read().splitlines()):
            strings[message] = line_num
    for lang_code in available_languages():
        with open('translations/' + lang_code + '.txt') as lang:
            translations[lang_code] = lang.read().splitlines()


def message(string, lang_code):
    if lang_code == 'en':
        return string
    line_num = strings[string]
    return translations[lang_code][line_num]


def available_languages():
    return [filename[:-4] for filename in os.listdir('translations')]

