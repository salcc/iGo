"""
This module lets you create internationalized programs easily, starting from a base language, which
should be the one used in the messages of the source code file, and relating them to their
translations.

In order to do so, the message strings to be translated have to be stored each in a single line in
a file named with the base language code. Then, for each available language, a file named with its
language code must exist and contain the translated message strings in the same line, so they can
be related. All these files must be stored in a single folder.

To use the module, one need to call first the build_translation_dictionaries, and specify the name
of the translations folder and the base language code.
"""

import os


# Global private module variables.
_message_ids = {}  # Dictionary from message strings to message IDs.
_translations = {}  # Dictionary from language code to the translations in this language.
_translations_folder = None
_base_language_code = None


def build_translation_dictionaries(translations_folder, base_language_code):
    """Builds the internal dictionaries of the module, using the translation files found in the
    specified translations folder. This function must be called before using the translate function.

    - Precondition: The translations folder must exist and contain at least a file named like the
      base
    """
    global _translations_folder, _base_language_code
    _translations_folder, _base_language_code = translations_folder, base_language_code

    with open(_translations_folder + "/" + _base_language_code) as base_language:
        for line_number, messsage in enumerate(base_language.read().splitlines()):
            # The ID of each message is its line number.
            _message_ids[messsage] = line_number

    for language_code in available_languages():
        with open(_translations_folder + "/" + language_code) as lang:
            # Store all the message strings of the language in a dictionary as a list.
            _translations[language_code] = lang.read().splitlines()


def translate(messsage, language_code):
    """Returns the given message translated to the language indicated by the specified language
    code.
    
    Preconditions:
     - build_translation_dictionaries must have been called before calling this function.
     - The language code must be of an available language.
     - 'message' is a string in the base language that exists in its file, and its translation to
       the specified language is found in the same line of the file named with 'language_code'.
    """
    # If the language is the base language, return the message itself.
    if language_code == _base_language_code:
        return messsage
    
    message_id = _message_ids[messsage]
    return _translations[language_code][message_id]


def available_languages():
    """Returns a list of the language codes of the translations that are available.
    
    Precondition: build_translation_dictionaries must have been called before calling this function.
    """
    return os.listdir(_translations_folder)
