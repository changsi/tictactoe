import boto3
import json
import logging
import re

from boto3.dynamodb.conditions import Key, Attr

expected_token = "3DcMzU48VP3UxK8Gnq0RWUkZ"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

form = '''\n
| %s | %s | %s |
-------------
| %s | %s | %s |
-------------
| %s | %s | %s |
'''  

winning_combos = (
    [6, 7, 8], [3, 4, 5], [0, 1, 2], [0, 3, 6], [1, 4, 7], [2, 5, 8],
    [0, 4, 8], [2, 4, 6],
)

def lambda_handler(event, context):
    logger.info(event)

    token = event['token']
    if token != expected_token:
        logger.error("Request token (%s) does not match exptected", token)
        raise Exception("Invalid request token")

    user = event['user_name']
    command = event['command']
    channel = event['channel_name']
    command_text = event['text']
    if command_text.startswith('start'):
        m = re.search('@([A-Za-z0-9_]+)', command_text)
        user2 = m.group(0)
        return _start_game(user, user2, channel)
    elif command_text.startswith('quite'):
        return _quite_game(channel)
    elif command_text.startswith('help'):
        return _wrap_response(_help())
    elif command_text.startswith('show'):
        return _show_game(channel)
    else:
        return _make_move(user, channel, command_text.strip())

def _load_game(channel):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('tictactoe')
    response = table.get_item(
        Key={
            'channel': channel
        }
    )
    logger.info(response)
    return response.get('Item', None)

def _start_game(user1, user2, channel):
    game = _load_game(channel)
    if game:
        return _wrap_response("There is already a ongoing game played by @{} and @{}.".format(game['user1'], game['user2']))
    if not user2:
        return _wrap_response("Please invite another user to play with you.")
    else:
        user2=user2[1:]
        game = {
            "board": range(1,10),
            "user1": user1,
            "user2": user2,
            "channel": channel,
            "nextPlayer": user1,
            "nextPlayerLabel": "X"
        }
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('tictactoe')
        table.put_item(Item=game)
        response = "@{} invite @{} to play Tic Tac Toe. \n @{}: it is your turn to play. Your label is X.\n @{}: your label is O.".format(user1, user2, user1, user2)
        response += _help()
        return _wrap_response(response)

def _show_game(channel):
    game = _load_game(channel)
    if not game:
        return _wrap_reponse("Sorry, there is no ongoing game.")
    board = game['board']
    response = _print_board(board)
    response += "\n @{} and @{} is playing the game, and it is @{} turn.".format(game['user1'], game['user2'], game['nextPlayer'])
    return _wrap_response(response)

def _wrap_response(message):
    return {
        "response_type": "in_channel",
        "text": message
    }

def _help():
    response = _print_board(range(1,10))
    response += '''
The game board has 9 sqaures(3X3).
Two players take turns in marking the spots/grids on the board.
The first player to have 3 pieces in a horizontal, vertical or diagonal row wins the game.
To place your mark in the desired square, simply type the number corresponding with the square on the grid 
Type "quit" to quite.
Type "start @{user}" to start a game. For example "start @sichang"
Type "show" to show current status of the game.
    '''
    return response

def _print_board(board = None):
    return form % tuple(board[6:9] + board[3:6] + board[0:3])

def _is_space_free(board, index):
    return board[index] in [1,2,3,4,5,6,7,8,9]

def _make_move(user, channel, move):
    game = _load_game(channel)
    if not game:
        return _wrap_reponse("Sorry, please start a game first.")
    board = game['board']

    if move not in ['1','2','3','4','5','6','7','8','9']:
        return _wrap_response("@{} Invalid move. Please try again: (1-9)".format(user))
    move = int(move)
    if not _is_space_free(board,move-1):
        return _wrap_response("@{} Invalid move. Space is not free.".format(user))
    elif game['nextPlayer'] != user:
        return _wrap_response("@{} Invalid move. Not your turn.".format(user))
    board[move-1] = game['nextPlayerLabel']
    _update_game(channel, game, user)
    
    response = _print_board(board)
    if _is_winner(board, game['nextPlayerLabel']):
        _delete_game(channel)
        response += "\n {} win the game. Game over!".format(user)
    elif _is_board_full(board):
        _delete_game(channel)
        response += "\n Board is full. Game over!"
    return _wrap_response(response)

def _update_game(channel, game, user):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('tictactoe')
    response = table.update_item(
        Key={
            'channel': channel
        },
        UpdateExpression="set board=:board, nextPlayer=:nextPlayer, nextPlayerLabel=:nextPlayerLabel",
        ExpressionAttributeValues={
            ':board': game['board'],
            ':nextPlayer': game['user2'] if game['user1'] == user else game['user1'],
            ':nextPlayerLabel': 'O' if game['nextPlayerLabel'] == 'X' else 'X'
        },
        ReturnValues="UPDATED_NEW"
    )

def _is_winner(board, label):
    for combo in winning_combos:
        if (board[combo[0]] == board[combo[1]] == board[combo[2]] == label):
            return True
    return False

def _is_board_full(board):
    for i in range(1,9):
        if _is_space_free(board, i):
            return False
    return True
    
def _quite_game(channel):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('tictactoe')
    response = table.get_item(
        Key={
            'channel': channel
        }
    )
    logger.info(response)
    game = response.get('Item', None)
    if not game:
        return _wrap_response("You have not start a game yet!")
    isSuccessful = _delete_game(channel)
    if isSUccessfull:
        response = _print_board(game['board'])
        return _wrap_response(response + "Quite game!")
    else:
        return _wrap_response("Fail to quite game!")

def _delete_game(channel):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('tictactoe')
    try:
        response = table.delete_item(
            Key={
                'channel': channel
            }
        )
    except ClientError as e:
        logger.error(e.response['Error']['Message'])
        return False
    else:
        return True
        
