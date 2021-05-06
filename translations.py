def message(string, language):
    strings = {
        'catalan': {
            'Hi! 😄': 'Hola! 😄',
            'I\'m iGo and I\'ll help you go to wherever you want as quick as a flash. ⚡': 'Soc l\'iGo, i t\'ajudaré a anar on vulguis ràpid com un llamp. ⚡',
            'You can use the command /help to see everything I can do.': 'Pots fer servir la comanda /help per veure tot el que puc fer.',
            'Do you want to update your location?': 'Vols actualitzar la teva ubicació?',
            'I need to know your location, do you mind sharing it with me?': 'Necessito saber la teva ubicació, et sembla bé compartir-me-la?',
            'Oooh! So you want to go to ': 'Oooh! Així que vols anar a ',
            'I\'m sorry, there are no results for ': 'Ho sento, no hi ha resultats per a ',
            'I\'ll show you where you are.': 'T\'ensenyaré on ets.',
            'Share location': 'Compartir ubicació',
            'Tell me where you are.': 'Envia\'m on ets.',
            'Processing...': 'Processant...',
            'Operation cancelled.': 'Operació cancel·lada.',
            'Uuuh... You are already here!': 'Vaja, si ja hi ets!',
            'Your location has been updated.': 'La teva ubicació ha estat actualitzada.',
            'Yes': 'Sí',
            'No': 'No',
            'Cancel': 'Cancel·lar',
        },
        'spanish': {
            'Hi! 😄': '¡Hola! 😄',
            'I\'m iGo and I\'ll help you go to wherever you want as quick as a flash. ⚡': 'Soy iGo, y te ayudaré a ir a donde quieras rápido como un rayo. ⚡',
            'You can use the command /help to see everything I can do.': 'Puedes usar la comanda /help para ver todo lo que puedo hacer.',
            'Do you want to update your location?': '¿Quieres actualizar tu ubicación?',
            'I need to know your location, do you mind sharing it with me?': 'Necesito saber tu ubicación, ¿te parece bien compartírmela?',
            'Oooh! So you want to go to ': '¡Oooh! Así que quieres ir a ',
            'I\'m sorry, there are no results for ': 'Lo siento, no hay resultados para ',
            'I\'ll show you where you are.': 'Te enseñaré dónde estás.',
            'Share location': 'Compartir ubicación',
            'Tell me where you are.': 'Dime dónde estás.',
            'Processing...': 'Procesando...',
            'Operation cancelled.': 'Operación cancelada.',
            'Uuuh... You are already here!': 'Vaya, ¡si ya estás ahí!',
            'Your location has been updated.': 'Tu ubicación ha sido actualizada.',
            'Yes': 'Sí',
            'No': 'No',
            'Cancel': 'Cancelar',
        },
        'uwu': {

        }
    }

    if language in strings:
        return strings[language][string]
    return string
