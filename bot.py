# importa l'API de Telegram

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext
import igo
import os
import re

PLACE = 'Barcelona, Barcelonés, Barcelona, Catalonia'
GRAPH_FILENAME = 'graph.dat'
HIGHWAYS_FILENAME = 'highways.dat'
SIZE = 1200
HIGHWAYS_URL = 'https://opendata-ajuntament.barcelona.cat/data/dataset/1090983a-1c40-4609-8620-14ad49aae3ab/resource/1d6c814c-70ef-4147-aa16-a49ddb952f72/download/transit_relacio_trams.csv'
CONGESTIONS_URL = 'https://opendata-ajuntament.barcelona.cat/data/dataset/8319c2b1-4c21-4962-9acd-6db4c5ff1148/resource/2d456eb5-4ea6-4f68-9794-2f3f1a58a933/download'

share_location_button = InlineKeyboardButton('M\'he mogut', callback_data='1')
same_location_button = InlineKeyboardButton('Soc on era', callback_data='2')
cancel_button = InlineKeyboardButton('Cancel·lar', callback_data='64')
markup = InlineKeyboardMarkup([[share_location_button], [same_location_button], [cancel_button]])

pos_coordinates_regex = re.compile(r'-?[1-9][0-9]*(\.[0-9]+)?[,\s]\s*-?[1-9][0-9]*(\.[0-9]+)?')
separator_regex = re.compile(r'[,\s]\s*')

# defineix una funció que saluda i que s'executarà quan el bot rebi el missatge /start
def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Hola! Em dic Jaume, i et portaré on em manis, d-daddy UwU")


def go(update, context):
    context.user_data['function'] = 'go'
    destination = update.message.text[4:]
    context.bot.send_message(chat_id=update.effective_chat.id, text="Oooh!! Així que vols anar a " + destination + "?")
    try:
        context.user_data['destination'] = igo.name_to_coordinates(destination, PLACE)
        context.bot.send_message(chat_id=update.effective_chat.id, text="On ets?", reply_markup=markup)
    except:
        context.bot.send_message(chat_id=update.effective_chat.id, text="No ho he tubat buaaa 😭")


def query_handler(update, context):
    query = update.callback_query
    action = query.data
    if action == '1':
        query.delete_message()
        share_location_button = KeyboardButton('Compartir ubicació', request_location=True)
        cancel_button = KeyboardButton('Cancel·lar')
        markup = ReplyKeyboardMarkup([[share_location_button], [cancel_button]], resize_keyboard=True, one_time_keyboard=True)
        context.bot.send_message(chat_id=update.effective_chat.id, text="Envia'm on ets.", reply_markup=markup)
    elif action == '2':
        query.edit_message_text('Buscant el camí')
        if 'location' in context.user_data:
            if context.user_data['function'] == 'go':
                plot_path(update, context)
            elif context.user_data['function'] == 'where':
                plot_location(update, context)
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text="No et tobuu buaaa 😭")
    elif action == '64':
        query.edit_message_text('Operació cancel·lada')
    query.answer()


def plot_path(update, context):
    congestions = igo.download_congestions(CONGESTIONS_URL)

    igraph = igo.build_igraph(graph, highways, congestions)
    origin = context.user_data['location']
    destination = igo.coordinates_to_node(graph, context.user_data['destination'])
    ipath = igo.get_ipath(igraph, origin, destination)

    path_plot = igo.get_path_plot(ipath, SIZE)
    filename = 'ipath-{}-{}.png'.format(origin, destination)
    igo.save_image(path_plot, filename)
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(filename, 'rb'))
    os.remove(filename)


def where(update, context):
    context.user_data['function'] = 'where'
    context.bot.send_message(chat_id=update.effective_chat.id, text="On ets?", reply_markup=markup)


def plot_location(update, context):
    location = context.user_data['location']
    filename = 'location-{}.png'.format(location)
    location = igo.node_to_coordinates(graph, location)
    location_plot = igo.get_location_plot(location, SIZE)
    igo.save_image(location_plot, filename)
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(filename, 'rb'))
    os.remove(filename)


def location_handler(update, context):
    context.user_data['location'] = igo.coordinates_to_node(graph, (update.message.location.latitude, update.message.location.longitude)) # TODO
    if context.user_data['function'] == 'go':
        context.bot.send_message(chat_id=update.effective_chat.id, text="Buscant el camí")
        plot_path(update, context)
    elif context.user_data['function'] == 'where':
        plot_location(update, context)


def pos(update, context):
    location = update.message.text[5:].strip()
    if pos_coordinates_regex.fullmatch(location):
        lon, lat = re.split(separator_regex, location)
        coordinates = igo.Coordinate(float(lon), float(lat))
    else:
        try:
            coordinates = igo.name_to_coordinates(location, PLACE)
        except:
            context.bot.send_message(chat_id=update.effective_chat.id, text="No ho he tubat buaaa 😭")
            return
    context.user_data['location'] = igo.coordinates_to_node(graph, coordinates)
    context.bot.send_message(chat_id=update.effective_chat.id, text="La teva ubicació ha estat actualitzada.")


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

    # declara una constant amb el access token que llegeix de token.txt
    TOKEN = open('token.txt').read().strip()

    # crea objectes per treballar amb Telegram
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('go', go))
    dispatcher.add_handler(CommandHandler('where', where))
    dispatcher.add_handler(CommandHandler('pos', pos))
    dispatcher.add_handler(CallbackQueryHandler(query_handler))
    dispatcher.add_handler(MessageHandler(Filters.location, location_handler))

    # engega el bot
    updater.start_polling()

    print("Bot running")
