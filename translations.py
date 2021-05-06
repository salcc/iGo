def message(string, language):
    strings = {
        'catalan': {
            'Hi! 😄': 'Hola! 😄',
            'I\'m iGo and I\'ll help you go to wherever you want as quick as a flash. ⚡': 'Soc l\'iGo, i t\'ajudaré a anar on vulguis ràpid com un llampèc. ⚡',
            'You can use the command /help to see what I can do.': 'Pots fer servir la comanda /help per a veure tot el que puc fer.',
            'Do you want to update your location?': 'Vols actualitzar la teva ubicació?',
            'I need to know your location, do you mind sharing it with me?': 'Necessito saber la teva ubicació, et sembla bé compartir-me-la?',
            'Oooh! So you want to go to ': 'Oooh! Així que vols anar a ',
            'I\'m sorry, there are no results for ': 'Ho sento, no hi ha resultats per a ',
            'I\'ll show you where you are.': 'T\'ensenyaré on ets.',
            'Share location': 'Compartir ubicació',
            'Send me where you are.': 'Envia\'m on ets',
            'Processing...': 'Processant...',
            'Operation cancelled.': 'Operació cancel·lada.',
            'Uuuh... You are already here!': 'Vaja, si ja hi ets!',
            'Your location has been updated.': 'La teva ubicació ha estat actualitzada.',
            'Yes': 'Sí',
            'No': 'No',
            'Cancel': 'Cancel·lar',
        },
        'spanish': {

        },
        'french': {

        },
        'uwu': {

        }
    }

    if language in strings:
        return strings[language][string]
    return string
