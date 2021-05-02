# importa l'API de Telegram
from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import igo
import os

PLACE = 'Barcelona, Barcelonés, Barcelona, Catalonia'
GRAPH_FILENAME = 'graph.dat'
HIGHWAYS_FILENAME = 'highways.dat'
SIZE = 2000
HIGHWAYS_URL = 'https://opendata-ajuntament.barcelona.cat/data/dataset/1090983a-1c40-4609-8620-14ad49aae3ab/resource/1d6c814c-70ef-4147-aa16-a49ddb952f72/download/transit_relacio_trams.csv'
CONGESTIONS_URL = 'https://opendata-ajuntament.barcelona.cat/data/dataset/8319c2b1-4c21-4962-9acd-6db4c5ff1148/resource/2d456eb5-4ea6-4f68-9794-2f3f1a58a933/download'


# defineix una funció que saluda i que s'executarà quan el bot rebi el missatge /start
def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Hola! Em dic Jaume, i et portaré on em manis, d-daddy UwU")
    if 'graph' not in context.bot_data:
        context.bot_data['graph'] = igo.load_data(GRAPH_FILENAME)
    if 'highways' not in context.bot_data:
        context.bot_data['highways'] = igo.load_data(HIGHWAYS_FILENAME)


def go(update, context):
    context.user_data['function'] = 'go'
    destination = update.message.text[4:]
    context.bot.send_message(chat_id=update.effective_chat.id, text="Oooh!! Així que vols anar a " + destination + "?")
    try:
        context.user_data['destination'] = igo.name_to_coordinates(destination, PLACE)
        markup = ReplyKeyboardMarkup([[KeyboardButton('Compartir ubicació', request_location=True)]], resize_keyboard=True,
                                 one_time_keyboard=True)
        context.bot.send_message(chat_id=update.effective_chat.id, text="Envia'm on ets.", reply_markup=markup)

    except:
        context.bot.send_message(chat_id=update.effective_chat.id, text="No ho he tubat buaaa 😭")


def path(update, context):
    graph = context.bot_data['graph']
    highways = context.bot_data['highways']
    congestions = igo.download_congestions(CONGESTIONS_URL)

    igraph = igo.build_igraph(graph, highways, congestions)
    origin = context.user_data['origin']
    destination = igo.coordinates_to_node(graph, context.user_data['destination'])
    ipath = igo.get_ipath(igraph, origin, destination)

    path_plot = igo.get_path_plot(ipath, SIZE)
    igo.save_image(path_plot, 'ipath.png')
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=open('ipath.png', 'rb'))
    os.remove('ipath.png')


def location(update, context):
    graph = context.bot_data['graph']
    context.user_data['origin'] = igo.coordinates_to_node(graph, (update.message.location.latitude, update.message.location.longitude))
    if context.user_data['function'] == 'go':
        path(update, context)
    elif context.user_data['funcion'] == 'where':
        pass


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

    # declara una constant amb el access token que llegeix de token.txt
    TOKEN = open('token.txt').read().strip()

    # crea objectes per treballar amb Telegram
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # indica que quan el bot rebi la comanda /start s'executi la funció start
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('go', go))

    dispatcher.add_handler(MessageHandler(Filters.location, location))

    # engega el bot
    updater.start_polling()

    print("Bot running")