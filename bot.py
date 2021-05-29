import os
from datetime import datetime
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
import igo
from translations import translate, available_languages, build_translation_dictionaries


def get_language(update, context):
    if "language" not in context.user_data:
        language_code = update.message.from_user.language_code
        if language_code not in available_languages():
            language_code = "en"
        context.user_data["language"] = language_code

    return context.user_data["language"]


def start(update, context):
    lang = get_language(update, context)

    context.bot.send_message(chat_id=update.effective_chat.id, text=translate("Hi!", lang) + " 😄")
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=translate("I'm iGo and I'll help you go to wherever you want as quick as a flash.", lang)
                                  + " ⚡")
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=translate("You can use the command /help to see everything I can do.", lang) + " 👀")


def location_keyboards(update, context):
    lang = get_language(update, context)

    new_location_button = InlineKeyboardButton(translate("Yes", lang), callback_data="1")
    same_location_button = InlineKeyboardButton(translate("No", lang), callback_data="2")
    cancel_button = InlineKeyboardButton(translate("Cancel", lang), callback_data="64")

    if "location" in context.user_data:
        markup = InlineKeyboardMarkup([[new_location_button, same_location_button], [cancel_button]])
        context.bot.send_message(chat_id=update.effective_chat.id, text=translate("Do you want to update your location?", lang),
                                 reply_markup=markup)
    else:
        markup = InlineKeyboardMarkup([[new_location_button], [cancel_button]])
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=translate("I need to know your location, do you mind sharing it with me?", lang) + " 😊",
                                 reply_markup=markup)


def get_coordinates(context, update, place_name, place):
    lang = get_language(update, context)

    if place_name:
        try:
            return igo.name_to_coordinates(place_name, place, "lat-lng")
        except ValueError:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=translate("I'm sorry, there are no results for ", lang) + place_name +
                                          translate(" in Barcelona.", lang) + " 😥")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=translate("You haven't told me where you want to go!", lang) + " ☹️")


def go(update, context):
    lang = get_language(update, context)

    context.user_data["function"] = "go"
    destination = update.message.text[4:].strip()
    destination_coordinates = get_coordinates(context, update, destination, PLACE)
    if destination_coordinates:
        context.user_data["destination"] = destination_coordinates
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Oooh! 😃 " + translate("So you want to go to ", lang) + destination + ".")
        location_keyboards(update, context)


def where(update, context):
    lang = get_language(update, context)

    context.user_data["function"] = "where"
    context.bot.send_message(chat_id=update.effective_chat.id, text=translate("I'll show you where you are.", lang) + " 🗺️")
    location_keyboards(update, context)


def query_handler(update, context):
    lang = context.user_data["language"]

    query = update.callback_query
    action = query.data
    if action == "1":
        query.delete_message()
        share_location_button = KeyboardButton(translate("Share location", lang) + " 📍", request_location=True)
        markup = ReplyKeyboardMarkup([[share_location_button]], resize_keyboard=True, one_time_keyboard=True)
        context.bot.send_message(chat_id=update.effective_chat.id, text=translate("Send me your location.", lang) + " 🧐",
                                 reply_markup=markup)
    elif action == "2":
        query.edit_message_text(translate("Processing...", lang) + " ⏳")
        if context.user_data["function"] == "go":
            get_and_plot_path(update, context)
        elif context.user_data["function"] == "where":
            plot_location(update, context)
    elif action == "64":
        query.edit_message_text(translate("Operation cancelled.", lang) + " ❌")
    query.answer()


def get_dynamic_igraph(context):
    if not "last_congestions_update" in context.bot_data or \
        (datetime.now() - context.bot_data["last_congestions_update"]).total_seconds() / 60 >= 5:
        congestions = igo.download_congestions(CONGESTIONS_URL)
        dynamic_igraph = igo.build_dynamic_igraph(igraph, highway_paths, congestions)
        igo.save_data(dynamic_igraph, DYNAMIC_IGRAPH_FILENAME)
        context.bot_data["last_congestions_update"] = congestions[1].datetime
    else:
        dynamic_igraph = igo.load_data(DYNAMIC_IGRAPH_FILENAME)  # We do not have to check if it exists.
    return dynamic_igraph


def get_and_plot_path(update, context):
    lang = get_language(update, context)

    source = context.user_data["location"]
    destination = context.user_data["destination"]
    if source == destination:
        context.bot.send_message(chat_id=update.effective_chat.id, text=translate("Oh, you are already here!", lang) + " 🥳")
    else:
        dynamic_igraph = get_dynamic_igraph(context)
        ipath = igo.get_ipath(dynamic_igraph, source, destination)
        if ipath:
            ipath_plot = igo.get_ipath_plot(ipath, SIZE)
            filename = "ipath-{}-{}.png".format(source, destination)
            igo.save_map_as_image(ipath_plot, filename)
            context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(filename, "rb"))
            os.remove(filename)
        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=translate("The only way to get where you want is to pass a road that is closed!", lang)
                                          + " 😟")


def plot_location(update, context):
    location = context.user_data["location"]
    filename = "location-{}.png".format(location)
    location_plot = igo.get_location_plot(location, SIZE)
    igo.save_map_as_image(location_plot, filename)
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(filename, "rb"))
    os.remove(filename)


def location_handler(update, context):
    lang = get_language(update, context)

    coordinates = igo.Coordinates(update.message.location.longitude, update.message.location.latitude)
    context.bot.send_message(chat_id=update.effective_chat.id, text=translate("Processing...", lang) + " ⏳",
                             reply_markup=ReplyKeyboardRemove())
    if igo.is_in_place(coordinates, PLACE):
        context.user_data["location"] = coordinates
        if context.user_data["function"] == "go":
            get_and_plot_path(update, context)
        elif context.user_data["function"] == "where":
            plot_location(update, context)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=translate("You seem to be outside Barcelona. I'm afraid I can't help you here.", lang)
                                      + " 🤕")


def pos(update, context):
    lang = get_language(update, context)

    location = update.message.text[5:].strip()
    coordinates = get_coordinates(context, update, location, PLACE)
    if coordinates:
        context.user_data["location"] = coordinates
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=translate("Your location has been updated.", lang) + " ✅")


def help(update, context):
    lang = get_language(update, context)

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=translate("/go [destination] - I will show you a map with the fastest way to go from your "
                                            "current location (green marker) to the destination (red marker) that you tell me "
                                            "when you use the command. This path is calculated taking into account the time it "
                                            "takes to turn and the current traffic data of Barcelona.", lang) + " 🚗\n\n" +
                                  translate("/where - I will show you a map with your current location indicated with a green "
                                            "marker.", lang) + " 🗺️\n\n" +
                                  translate("/setlang [language code] - I will talk to you in the language you choose from "
                                            "Catalan [ca], Spanish [es] and English [en].", lang) + " 🌐\n\n" +
                                  translate("/author - I will tell you who has developed me.", lang) + "👸🏻🤴🏻")


def author(update, context):
    lang = get_language(update, context)

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=translate("I have been developed with ❤️ by Marçal Comajoan Cara and Laura Saéz Parés, two "
                                            "students of the Universitat Politècnica de Catalunya (UPC), as a part of a project "
                                            "for the Algorithmics and Programming II subject of the Data Science and Engineering "
                                            "Degree.", lang))


def setlang(update, context):
    lang = get_language(update, context)

    new_lang = update.message.text[9:].strip()
    if new_lang in available_languages():
        context.user_data["language"] = new_lang
        context.bot.send_message(chat_id=update.effective_chat.id, text=translate("Language updated.", new_lang) + " ✅")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text=translate("Language code not recognized.", lang) + " 😕")


if __name__ == "__main__":
    PLACE = "Barcelona, Barcelonés, Barcelona, Catalonia"
    DEFAULT_GRAPH_FILENAME = "graph.dat"
    STATIC_IGRAPH_FILENAME = "static_igraph.dat"
    DYNAMIC_IGRAPH_FILENAME = "dynamic_igraph.dat"
    HIGHWAYS_FILENAME = "highways.dat"
    SIZE = 1200
    HIGHWAYS_URL = "https://opendata-ajuntament.barcelona.cat/data/dataset/1090983a-1c40-4609-8620-14ad49aae3ab/resource/" \
                   "1d6c814c-70ef-4147-aa16-a49ddb952f72/download/transit_relacio_trams.csv"
    CONGESTIONS_URL = "https://opendata-ajuntament.barcelona.cat/data/dataset/8319c2b1-4c21-4962-9acd-6db4c5ff1148/resource/" \
                      "2d456eb5-4ea6-4f68-9794-2f3f1a58a933/download"

    # Build the dictionaries used for the bot message translations.
    build_translation_dictionaries("translations", "en")

    # Load the default graph, or build it if it does not exist (and save it for later).
    if igo.file_exists(DEFAULT_GRAPH_FILENAME):
        graph = igo.load_data(DEFAULT_GRAPH_FILENAME)
    else:
        graph = igo.build_default_graph(PLACE)
        igo.save_data(graph, DEFAULT_GRAPH_FILENAME)

    # Load the highway paths, or build them if they do not exist (and save them for later).
    if igo.file_exists(HIGHWAYS_FILENAME):
        highway_paths = igo.load_data(HIGHWAYS_FILENAME)
    else:
        highways = igo.download_highways(HIGHWAYS_URL)
        highway_paths = igo.build_highway_paths(graph, highways)
        igo.save_data(highway_paths, HIGHWAYS_FILENAME)

    # Load the static igraph, or build it if it does not exist (and save it for later).
    if igo.file_exists(STATIC_IGRAPH_FILENAME):
        igraph = igo.load_data(STATIC_IGRAPH_FILENAME)
    else:
        igraph = igo.build_static_igraph(graph)
        igo.save_data(igraph, STATIC_IGRAPH_FILENAME)

    # Read the bot acces token from the file 'token.txt'.
    with open("token.txt", "r") as file:
        TOKEN = file.read().strip()

    # Create the Updater and pass it the bot token.
    updater = Updater(token=TOKEN, use_context=True)

    # Get the dispatcher to register handlers.
    dispatcher = updater.dispatcher

    # Add handlers for all the bot commands.
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("go", go))
    dispatcher.add_handler(CommandHandler("where", where))
    dispatcher.add_handler(CommandHandler("pos", pos))
    dispatcher.add_handler(CommandHandler("help", help))
    dispatcher.add_handler(CommandHandler("author", author))
    dispatcher.add_handler(CommandHandler("setlang", setlang))

    # Add the handler used for the inline reply keyboards.
    dispatcher.add_handler(CallbackQueryHandler(query_handler))

    # Add the handler used for when a real user location is sent to the bot.
    dispatcher.add_handler(MessageHandler(Filters.location, location_handler))

    # Start the bot.
    updater.start_polling()
    print("Bot running.")

    # Run the bot until Ctrl+C is pressed.
    updater.idle()

    print()
    print("Bot dead.")
