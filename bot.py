import igo
from translations import message, available_languages, build_translation_dictionaries
import os
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler


PLACE = 'Barcelona, Barcelonés, Barcelona, Catalonia'
GRAPH_FILENAME = 'graph.dat'
HIGHWAYS_FILENAME = 'highways.dat'
SIZE = 1200
HIGHWAYS_URL = 'https://opendata-ajuntament.barcelona.cat/data/dataset/1090983a-1c40-4609-8620-14ad49aae3ab/resource/1d6c814c-70ef-4147-aa16-a49ddb952f72/download/transit_relacio_trams.csv'
CONGESTIONS_URL = 'https://opendata-ajuntament.barcelona.cat/data/dataset/8319c2b1-4c21-4962-9acd-6db4c5ff1148/resource/2d456eb5-4ea6-4f68-9794-2f3f1a58a933/download'


def get_language(update, context):
    if 'language' not in context.user_data:
        context.user_data['language'] = update.message.from_user.language_code
    return context.user_data['language']

# defineix una funció que saluda i que s'executarà quan el bot rebi el missatge /start
def start(update, context):
    lang = get_language(update, context)

    context.bot.send_message(chat_id=update.effective_chat.id, text=message('Hi!', lang) + ' 😄')
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=message('I\'m iGo and I\'ll help you go to wherever you want as quick as a flash.', lang) + ' ⚡')
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=message('You can use the command /help to see everything I can do.', lang) + ' 👀')


def location_keyboards(update, context):
    lang = get_language(update, context)

    new_location_button = InlineKeyboardButton(message('Yes', lang), callback_data='1')
    same_location_button = InlineKeyboardButton(message('No', lang), callback_data='2')
    cancel_button = InlineKeyboardButton(message('Cancel', lang), callback_data='64')

    if 'location' in context.user_data:
        markup = InlineKeyboardMarkup([[new_location_button, same_location_button], [cancel_button]])
        context.bot.send_message(chat_id=update.effective_chat.id, text=message('Do you want to update your location?', lang),
                                 reply_markup=markup)
    else:
        markup = InlineKeyboardMarkup([[new_location_button], [cancel_button]])
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=message('I need to know your location, do you mind sharing it with me?', lang) + ' 😊',
                                 reply_markup=markup)

def get_coordinates(place_name, place):
    try:
        coordinates = igo.name_to_coordinates(place_name, place)
    except:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                text=message('I\'m sorry, there are no results for ', lang) + destination + message(' a Barcelona.', lang) + ' 😥')
        return None
    return coordinates


def go(update, context):
    lang = get_language(update, context)

    context.user_data['function'] = 'go'
    destination = update.message.text[4:].strip()
    if destination:            
        destination_coordinates = get_coordinates(destination, PLACE)
        if destination_coordinates:
            context.user_data['destination'] = destination_coordinates
            context.bot.send_message(chat_id=update.effective_chat.id,
                                text='Oooh! 😃 ' +  message('So you want to go to ', lang) + destination + '.')
        location_keyboards(update, context)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=message('You haven\'t told me where you want to go!', lang) + ' ☹️')


def where(update, context):
    lang = get_language(update, context)

    context.user_data['function'] = 'where'
    context.bot.send_message(chat_id=update.effective_chat.id, text=message('I\'ll show you where you are.', lang) + ' 🗺️')
    location_keyboards(update, context)


def query_handler(update, context):
    lang = context.user_data['language']

    query = update.callback_query
    action = query.data
    if action == '1':
        query.delete_message()
        share_location_button = KeyboardButton(message('Share location', lang) + ' 📍', request_location=True)
        markup = ReplyKeyboardMarkup([[share_location_button]], resize_keyboard=True, one_time_keyboard=True)
        context.bot.send_message(chat_id=update.effective_chat.id, text=message('Send me your location.', lang) + ' 🧐',
                                 reply_markup=markup)

    elif action == '2':
        query.edit_message_text(message('Processing...', lang) + ' ⏳')
        if context.user_data['function'] == 'go':
            plot_path(update, context)
        elif context.user_data['function'] == 'where':
            plot_location(update, context)
    elif action == '64':
        query.edit_message_text(message('Operation cancelled.', lang) + ' ❌')
    query.answer()


def plot_path(update, context):
    lang = get_language(update, context)

    origin = context.user_data['location']
    destination = igo.coordinates_to_node(graph, context.user_data['destination'])
    if origin == destination:
        context.bot.send_message(chat_id=update.effective_chat.id, text=message('Oh, you are already here!', lang) + ' 🥳')
    else:
        congestions = igo.download_congestions(CONGESTIONS_URL)
        igraph = igo.build_igraph(graph, highways, congestions)
        ipath = igo.get_ipath(igraph, origin, destination)
        if ipath:    
            path_plot = igo.get_path_plot(ipath, SIZE)
            filename = 'ipath-{}-{}.png'.format(origin, destination)
            igo.save_image(path_plot, filename)
            context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(filename, 'rb'))
            os.remove(filename)
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text=message('The only way to get where you want is to pass a road that is closed!', lang) + ' 😟')


def plot_location(update, context):
    location = context.user_data['location']
    filename = 'location-{}.png'.format(location)
    location = igo.node_to_coordinates(graph, location)
    location_plot = igo.get_location_plot(location, SIZE)
    igo.save_image(location_plot, filename)
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(filename, 'rb'))
    os.remove(filename)


def location_handler(update, context):
    lang = get_language(update, context)

    coordinates = igo.Coordinates(update.message.location.latitude, update.message.location.longitude)
    context.bot.send_message(chat_id=update.effective_chat.id, text=message('Processing...', lang) + ' ⏳',
                                reply_markup=ReplyKeyboardRemove())
    if igo.is_in_place(coordinates, PLACE):
        context.user_data['location'] = igo.coordinates_to_node(graph, coordinates)
        if context.user_data['function'] == 'go':
            plot_path(update, context)
        elif context.user_data['function'] == 'where':
            plot_location(update, context)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text=message('You seem to be outside Barcelona. I\'m afraid I can\'t help you here.', lang) + ' 🤕')


def pos(update, context):
    lang = get_language(update, context)

    location = update.message.text[5:].strip()
    try:
        coordinates = igo.name_to_coordinates(location, PLACE)
        if not igo.is_in_place(coordinates, PLACE):
            raise Exception
    except Exception:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                    text=message('I\'m sorry, there are no results for ', lang) + location + '. 😥')
        return
    context.user_data['location'] = igo.coordinates_to_node(graph, coordinates)
    context.bot.send_message(chat_id=update.effective_chat.id, text=message('Your location has been updated.', lang) + '✅')


def help(update, context):
    lang = get_language(update, context)

    context.bot.send_message(chat_id=update.effective_chat.id, 
                             text=message('/go [destination] - I will show you a map with the fastest way to go from your current location '
                                '(green marker) to the destination (red marker) that you tell me when you use the command. This '
                                'path is calculated taking into account the current traffic data of Barcelona.', lang) + ' 🚗\n\n' +
                                message('/where - I will show you a map with your current location indicated with a green marker.', lang)
                                + ' 🗺️\n\n' + message('/setlang [language code] - I will talk to you in the language you choose from '
                                'Catalan [ca], Spanish [es] and English [en].', lang) + ' 🌐\n\n' + message('/author - I will tell you '
                                'who has developed me.', lang) + '👸🏻🤴🏻'
                                 )


def author(update, context):
    lang = get_language(update, context)
    
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=message(
                                 'I have been developed with ❤️ by Marçal Comajoan Cara and Laura Saéz Parés, '
                                 'two students of the Universitat Politècnica de Catalunya (UPC), as a part of a project for the '
                                 'Algorithmics and Programming II subject of the Data Science and Engineering Degree.', lang))


def setlang(update, context):
    lang = get_language(update, context)

    new_lang = update.message.text[9:].strip()
    if new_lang in available_languages():
        context.user_data['language'] = new_lang
        context.bot.send_message(chat_id=update.effective_chat.id, text=message('Language updated.', new_lang) + ' ✅')
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text=message('Language code not recognized.', lang) + ' 😕')


if __name__ == '__main__':
    build_translation_dictionaries()


    if not igo.file_exists(GRAPH_FILENAME):
        graph = igo.download_graph(PLACE)
        graph = igo.build_graph(graph)
        igo.save_data(graph, GRAPH_FILENAME)
    else:
        graph = igo.load_data(GRAPH_FILENAME)

    if not igo.file_exists(HIGHWAYS_FILENAME):
        highways = igo.download_highways(HIGHWAYS_URL)
        highways = igo.get_highway_paths(graph, highways)
        igo.save_data(highways, HIGHWAYS_FILENAME)
    else:
        highways = igo.load_data(HIGHWAYS_FILENAME)

    # declara una constant amb l'access token que llegeix de token.txt
    TOKEN = open('token.txt').read().strip()

    # crea objectes per treballar amb Telegram
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('go', go))
    dispatcher.add_handler(CommandHandler('where', where))
    dispatcher.add_handler(CommandHandler('pos', pos))
    dispatcher.add_handler(CommandHandler('help', help))
    dispatcher.add_handler(CommandHandler('author', author))
    dispatcher.add_handler(CommandHandler('setlang', setlang))

    dispatcher.add_handler(CallbackQueryHandler(query_handler))
    dispatcher.add_handler(MessageHandler(Filters.location, location_handler))

    # engega el bot
    updater.start_polling()

    print("Bot running")
