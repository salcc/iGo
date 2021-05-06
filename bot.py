# importa l'API de Telegram

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
import igo
import os
import re

from translations import message, available_languages

PLACE = 'Barcelona, Barcelonés, Barcelona, Catalonia'
GRAPH_FILENAME = 'graph.dat'
HIGHWAYS_FILENAME = 'highways.dat'
SIZE = 1200
HIGHWAYS_URL = 'https://opendata-ajuntament.barcelona.cat/data/dataset/1090983a-1c40-4609-8620-14ad49aae3ab/resource/1d6c814c-70ef-4147-aa16-a49ddb952f72/download/transit_relacio_trams.csv'
CONGESTIONS_URL = 'https://opendata-ajuntament.barcelona.cat/data/dataset/8319c2b1-4c21-4962-9acd-6db4c5ff1148/resource/2d456eb5-4ea6-4f68-9794-2f3f1a58a933/download'

pos_coordinates_regex = re.compile(r'-?[1-9][0-9]*(\.[0-9]+)?[,\s]\s*-?[1-9][0-9]*(\.[0-9]+)?')
separator_regex = re.compile(r'[,\s]\s*')


# defineix una funció que saluda i que s'executarà quan el bot rebi el missatge /start
def start(update, context):
    if 'language' not in context.user_data:
        context.user_data['language'] = update.message.from_user.language_code
    lang = context.user_data['language']

    context.bot.send_message(chat_id=update.effective_chat.id, text=message('Hi! 😄', lang))
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=message('I\'m iGo and I\'ll help you go to wherever you want as quick as a flash. ⚡', lang))
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=message('You can use the command /help to see everything I can do.', lang))


def location_keyboards(update, context):
    lang = context.user_data['language']

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
                                 text=message('I need to know your location, do you mind sharing it with me?', lang),
                                 reply_markup=markup)


def go(update, context):
    lang = context.user_data['language']

    context.user_data['function'] = 'go'
    destination = update.message.text[4:]
    try:
        context.user_data['destination'] = igo.name_to_coordinates(destination, PLACE)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=message('Oooh! So you want to go to ', lang) + destination + '.')
        location_keyboards(update, context)
    except:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=message('I\'m sorry, there are no results for ', lang) + destination + '.')


def where(update, context):
    lang = context.user_data['language']

    context.user_data['function'] = 'where'
    context.bot.send_message(chat_id=update.effective_chat.id, text=message('I\'ll show you where you are.', lang))
    location_keyboards(update, context)


def query_handler(update, context):
    lang = context.user_data['language']

    query = update.callback_query
    action = query.data
    if action == '1':
        query.delete_message()
        share_location_button = KeyboardButton(message('Share location', lang), request_location=True)
        markup = ReplyKeyboardMarkup([[share_location_button]], resize_keyboard=True, one_time_keyboard=True)
        context.bot.send_message(chat_id=update.effective_chat.id, text=message('Tell me where you are.', lang),
                                 reply_markup=markup)
    elif action == '2':
        query.edit_message_text(message('Processing...', lang))
        if context.user_data['function'] == 'go':
            plot_path(update, context)
        elif context.user_data['function'] == 'where':
            plot_location(update, context)
    elif action == '64':
        query.edit_message_text(message('Operation cancelled.', lang))
    query.answer()


def plot_path(update, context):
    lang = context.user_data['language']

    origin = context.user_data['location']
    destination = igo.coordinates_to_node(graph, context.user_data['destination'])
    if origin == destination:
        context.bot.send_message(chat_id=update.effective_chat.id, text=message('Uuuh... You are already here!', lang))
    else:
        congestions = igo.download_congestions(CONGESTIONS_URL)
        igraph = igo.build_igraph(graph, highways, congestions)
        ipath = igo.get_ipath(igraph, origin, destination)

        path_plot = igo.get_path_plot(ipath, SIZE)
        filename = 'ipath-{}-{}.png'.format(origin, destination)
        igo.save_image(path_plot, filename)
        context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(filename, 'rb'))
        os.remove(filename)


def plot_location(update, context):
    location = context.user_data['location']
    filename = 'location-{}.png'.format(location)
    location = igo.node_to_coordinates(graph, location)
    location_plot = igo.get_location_plot(location, SIZE)
    igo.save_image(location_plot, filename)
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(filename, 'rb'))
    os.remove(filename)


def location_handler(update, context):
    lang = context.user_data['language']

    coordinates = igo.Coordinates(update.message.location.latitude, update.message.location.longitude)
    context.user_data['location'] = igo.coordinates_to_node(graph, coordinates)
    context.bot.send_message(chat_id=update.effective_chat.id, text=message('Processing...', lang),
                             reply_markup=ReplyKeyboardRemove())
    if context.user_data['function'] == 'go':
        plot_path(update, context)
    elif context.user_data['function'] == 'where':
        plot_location(update, context)


def pos(update, context):
    lang = context.user_data['language']

    location = update.message.text[5:].strip()
    if pos_coordinates_regex.fullmatch(location):
        lng, lat = re.split(separator_regex, location)
        coordinates = igo.Coordinates(float(lat), float(lng))
    else:
        try:
            coordinates = igo.name_to_coordinates(location, PLACE)
        except:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=message('I\'m sorry, there are no results for ', lang) + location + '.')
            return
    context.user_data['location'] = igo.coordinates_to_node(graph, coordinates)
    context.bot.send_message(chat_id=update.effective_chat.id, text=message('Your location has been updated.', lang))


def help(update, context):
    pass  # TODO


def author(update, context):
    lang = context.user_data['language']

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=message(
                                 'The @Official_iGo_bot has been developed with ❤️ by Marçal Comajoan Cara and Laura Saéz Parés, '
                                 'students of the Polytechnic University of Catalonia (UPC), as a part of a project for the '
                                 'Algorithmics and Programming II subject of the Data Science and Engineering Degree.', lang))


def setlang(update, context):
    lang = update.message.text[9:].strip()
    if lang in available_languages():
        context.user_data['language'] = lang
        context.bot.send_message(chat_id=update.effective_chat.id, text=message('Language updated.', lang))
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text=message('Language not recognized.', lang))


if __name__ == '__main__':
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
