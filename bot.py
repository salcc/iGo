"""
The iGo Telegram bot shows users in Barcelona the most intelligent way of driving from their current 
location to their desired destination using the concept of itime.

To calculate the itime of a path, several data of Barcelona's road network is taken into account: 
the length and maximum driving speed of each street, the current traffic data available and the cost
of turning. The needed computations are handled by the igo module. 

The bot supports the following commands:
 - /go [destination]: Shows the user a map with the fastest way to go from their current location to
   the specified destination. 
 - /where: Shows the user a map with their current location.
 - /setlang [language code]: Sets the bot's language.
 - /author: Shows who has developed the bot.
 - /help: Shows a list of the available commands and what are they used for.
 - /pos [location]: Changes the user location to the specified one (intended for development).

The iGo bot is available in different languages. The translations of the shown messages are handled
by the translations module.
"""

from datetime import datetime
import os

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

from translations import translate, available_languages, build_translation_dictionaries
import igo


def get_language(update, context):
    """Returns the user's language. If the user has not previously specified a preferred language,
    the bot will use the one given by their Telegram settings if it is available, or English if it
    is not.
    """
    if "language" not in context.user_data:
        language_code = update.message.from_user.language_code
        if language_code not in available_languages():
            language_code = "en"
        context.user_data["language"] = language_code

    return context.user_data["language"]


def setlang(update, context):
    """Called when the /setlang [language code] command is executed. Updates the current bot 
    language to the specified language code. An error message is shown if it is not valid.
    """
    lang = get_language(update, context)

    new_lang = update.message.text[9:].strip()  # The first 9 characters are "/setlang ".
    if new_lang in available_languages():
        context.user_data["language"] = new_lang
        context.bot.send_message(chat_id=update.effective_chat.id, text=translate("Language updated.", new_lang) + " ✅")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text=translate("Language code not recognized.", lang) + " 😕")


def start(update, context):
    """Called when the /start command is executed. The bot introduces itself to the user and
    suggests them using /help to see its functionalities.
    """
    lang = get_language(update, context)

    context.bot.send_message(chat_id=update.effective_chat.id, text=translate("Hi!", lang) + " 😄")
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=translate("I'm iGo, and I'll help you go to wherever you want as quick as a flash.", lang)
                                  + " ⚡")
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=translate("You can use the command /help to see everything I can do.", lang) + " 👀")


def help(update, context):
    """Called when the /help command is executed. Shows the commands supported by the bot, and
    explains what they do.
    """
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
    """Called when the /author command is executed. Shows who developed the bot :)"""
    lang = get_language(update, context)

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=translate("I have been developed with ❤️ by Marçal Comajoan Cara and Laura Saéz Parés, two "
                                            "students of the Universitat Politècnica de Catalunya (UPC), as a part of a project "
                                            "for the Algorithmics and Programming II subject of the Data Science and Engineering "
                                            "Degree.", lang))


def ask_location(update, context):
    """Displays an inline keyboard which asks the user if they accept to share their location. If
    it already has the location, the bot asks the user if they want to update it, or to maintain the
    last shared one.

    When a button of the keyboard is pressed, the query_handler function is called automatically to
    handle which option the user has chosen.
    """
    lang = get_language(update, context)

    # Construct the inline keyboard buttons. callback_data is the ID of the chosen option, which is
    # used by the query_handler. It must be a string containing a number from 1 to 64.
    new_location_button = InlineKeyboardButton(translate("Yes", lang), callback_data="1")
    same_location_button = InlineKeyboardButton(translate("No", lang), callback_data="2")
    cancel_button = InlineKeyboardButton(translate("Cancel", lang), callback_data="64")

    if "location" in context.user_data:
        markup = InlineKeyboardMarkup([[new_location_button, same_location_button], [cancel_button]])
        context.bot.send_message(chat_id=update.effective_chat.id, text=translate("Do you want to update your location?", lang),
                                 reply_markup=markup)
    else:
        # If the bot does not have a location, do not show the same_location_button.
        markup = InlineKeyboardMarkup([[new_location_button], [cancel_button]])
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=translate("I need to know your location, do you want to share it with me?", lang) + " 😊",
                                 reply_markup=markup)


def query_handler(update, context):
    """Called when the user presses a button from the inline keyboard shown by the ask_location
    function. The function handles which option the user has chosen.

    If the user pressed that they want to share their real location, a button is displayed to do so.
    This button makes Telegram ask the user for their location, which then is handled by the
    location_handler function.

    Else if the user pressed that they want to maintain their location, get_and_plot_path or
    plot_location is called directly, depending on if the function that is being executed is "go"
    or "where".

    Else if the user pressed the Cancel button, nothing is done and the function being executed by
    the user is reset to None.
    """
    lang = context.user_data["language"]

    query = update.callback_query
    action = query.data
    if action == "1":  # The user wants to share their location.
        query.delete_message()
        share_location_button = KeyboardButton(translate("Share location", lang) + " 📍", request_location=True)
        markup = ReplyKeyboardMarkup([[share_location_button]], resize_keyboard=True, one_time_keyboard=True)
        context.bot.send_message(chat_id=update.effective_chat.id, text=translate("Send me your location.", lang) + " 🧐",
                                 reply_markup=markup)
    elif action == "2":  # The user does not want to update their location.
        query.edit_message_text(translate("Processing...", lang) + " ⏳")
        if context.user_data["function"] == "go":
            get_and_plot_path(update, context)
        elif context.user_data["function"] == "where":
            plot_location(update, context)
    elif action == "64":  # The user wants to cancel the operation.
        context.user_data["function"] = None
        query.edit_message_text(translate("Operation cancelled.", lang) + " ❌")
    query.answer()


def location_handler(update, context):
    """Called when the user sends a real location to the bot, which happens when they click the
    "Share location" button displayed by the query_handler function. Obtains the location
    coordinates and checks if they are inside the boundaries of PLACE. If that is the case, it 
    calls the get_and_plot_path or plot_location, depending on if the function that is being
    executed is "go" or "where". On the other side, if the user is not inside the boundaries of
    PLACE, an error message is shown.
    """
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


def get_coordinates(context, update, place_name):
    """Returns the coordinates given a string 'place_name', which can either be a geocodable string
    by the Nominatim API or a string representing a pair of latitude-longitude coordinates. If they
    include a decimal part, a dot '.' must be used as a decimal separator and they can be optionally
    separated by a comma.

    Two error messages can be shown: one if no place_name is specified, and another one if the
    Nominatim API can not find the given place name or the obtained coordinates are not inside the
    boundaries of PLACE.
    """
    lang = get_language(update, context)

    if place_name:
        try:
            return igo.name_to_coordinates(place_name, PLACE, coordinates_order="lat-lng")
        except ValueError:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=translate("I'm sorry, there are no results for ", lang) + place_name +
                                          translate(" in Barcelona.", lang) + " 😥")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=translate("You haven't told me where!", lang) + " ☹️")


def pos(update, context):
    """Called when the /pos [location] command is executed. Sets a false user location passed as an
    argument (which can either be the name of a place or a pair of latitude-longitude coordinates),
    and obtains its coordinates. A message is shown either confirming that the location has been
    updated, or giving an error if the argument is not valid (see get_coordinates).

    Note: /pos is a "secret" command  intended for testing the bot, so it is not shown when /help is
    executed.
    """
    lang = get_language(update, context)

    location = update.message.text[5:].strip()  # The first 5 characters are "/pos ".
    coordinates = get_coordinates(context, update, location)
    if coordinates:
        context.user_data["location"] = coordinates
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=translate("Your location has been updated.", lang) + " ✅")


def go(update, context):
    """Called when the the /go [destination] command is executed. Reads the destination argument,
    (which can either be the name of a place or a pair of latitude-longitude coordinates) obtains
    its coordinates, and sets that the current function the user is executing is "go". It then calls
    ask_location, which will continue the process of sending the user an image with the fastest path
    from their location to the specified destination.

    An error message is shown if the argument is not valid (see get_coordinates).
    """
    lang = get_language(update, context)

    destination = update.message.text[4:].strip()  # The first 4 characters are "/go ".
    destination_coordinates = get_coordinates(context, update, destination)
    if destination_coordinates:
        context.user_data["function"] = "go"
        context.user_data["destination"] = destination_coordinates
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Oooh! 😃 " + translate("So you want to go to ", lang) + destination + ".")
        ask_location(update, context)


def where(update, context):
    """Called when the /where command is executed. Sets that the current function the user is
    executing is "where". It then calls ask_location, which will continue the process of sending
    the user an image showing where they are.
    """
    lang = get_language(update, context)

    context.user_data["function"] = "where"
    context.bot.send_message(chat_id=update.effective_chat.id, text=translate("I'll show you where you are.", lang) + " 🗺️")
    ask_location(update, context)


def get_dynamic_igraph(context):
    """Returns a dynamic igraph, which is the data structure used to find the paths that the bot 
    shows to its users.

    The dynamic igraph is built if it has not been built already, or if it is older than five
    minutes, since it uses traffic data which is updated every five minutes.
    """
    if "last_congestions_update" not in context.bot_data or \
        (datetime.now() - context.bot_data["last_congestions_update"]).total_seconds() / 60 >= 5:
        congestions = igo.download_congestions(CONGESTIONS_URL)
        dynamic_igraph = igo.build_dynamic_igraph(igraph, highway_paths, congestions)
        igo.save_data(dynamic_igraph, DYNAMIC_IGRAPH_FILENAME)

        # Obtain the last congestions update datetime from the first Congestion (they are all the same).
        context.bot_data["last_congestions_update"] = congestions[1].datetime
    else:
        dynamic_igraph = igo.load_data(DYNAMIC_IGRAPH_FILENAME)  # We do not have to check if it exists.
    
    return dynamic_igraph


def get_and_plot_path(update, context):
    """Sends a map to the user showing the path from their current location (green marker) to their 
    specified destination (red marker) plotted with 5px Dodger Blue lines except for those that 
    connect the source and destination coordinates to the rest, which are Light Blue. 

    This path is the fastest possible considering the length of the streets, its maximum speeds,
    the current traffic data of Barcelona, and the cost of turning.

    An error message is shown if the user is already in their specified destination, and another one
    in the case the only way of going from their location to the destination is through a closed
    road.
    """
    lang = get_language(update, context)

    source = context.user_data["location"]
    destination = context.user_data["destination"]
    if source == destination:
        context.bot.send_message(chat_id=update.effective_chat.id, text=translate("Oh, you are already here!", lang) + " 🥳")
    else:
        dynamic_igraph = get_dynamic_igraph(context)
        ipath = igo.get_ipath(dynamic_igraph, source, destination)
        if ipath:
            path_plot = igo.get_ipath_plot(ipath, SIZE)
            send_plot(update, context, path_plot)
        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=translate("The only way to get where you want is to pass a road that is closed!", lang)
                                          + " 😟")


def plot_location(update, context):
    """Sends a map to the user showing the surroundings of their current location. A green marker is
    added at the exact point of their coordinates.
    """
    location = context.user_data["location"]
    location_plot = igo.get_location_plot(location, SIZE)
    send_plot(update, context, location_plot)


def send_plot(update, context, plot):
    """Sends an image to the user showing the given plot."""
    filename = str(hash(plot)) + ".png"  # Use the hash of the object 'plot' to make a unique filename.
    igo.save_map_as_image(plot, filename)
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(filename, "rb"))
    os.remove(filename)


# Call this code globally, because most of the variables here are used by the functions of the file,
# and can not be passed as parameters.
if __name__ == "__main__":
    # Constants.
    PLACE = "Barcelona, Barcelonés, Barcelona, Catalonia"
    DEFAULT_GRAPH_FILENAME = "graph.dat"
    STATIC_IGRAPH_FILENAME = "static_igraph.dat"
    DYNAMIC_IGRAPH_FILENAME = "dynamic_igraph.dat"
    HIGHWAYS_FILENAME = "highways.dat"
    SIZE = 1000
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
    print("Default graph loaded!")

    # Load the highway paths, or build them if they do not exist (and save them for later).
    if igo.file_exists(HIGHWAYS_FILENAME):
        highway_paths = igo.load_data(HIGHWAYS_FILENAME)
    else:
        highways = igo.download_highways(HIGHWAYS_URL)
        highway_paths = igo.build_highway_paths(graph, highways)
        igo.save_data(highway_paths, HIGHWAYS_FILENAME)
    print("Highway paths loaded!")

    # Load the static igraph, or build it if it does not exist (and save it for later).
    if igo.file_exists(STATIC_IGRAPH_FILENAME):
        igraph = igo.load_data(STATIC_IGRAPH_FILENAME)
    else:
        igraph = igo.build_static_igraph(graph)
        igo.save_data(igraph, STATIC_IGRAPH_FILENAME)
    print("Static igraph loaded!")

    # Read the bot access token from the file 'token.txt'.
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
    print("Bot running!")

    # Run the bot until Ctrl+C is pressed.
    updater.idle()

    print()
    print("Bot dead.")
