from flask import Flask, request, jsonify, render_template
from flask import Flask, send_from_directory
import os
import pyttsx3
import threading
from weather import get_weather
from datetime import datetime, timedelta
from pytz import timezone

# Import your other modules
from reminder import (
    parse_reminder_input,
    parse_date_expression,
    parse_time_expression,
    set_reminder,
    check_reminders,
    speak
)

from gcalendar import (
    get_calendar_service,
    create_event,
    parse_command,
    extract_date,
    extract_time
)


# Create Flask app

app = Flask(__name__, static_folder='static')


# Initialize TTS engine in a way that's thread-safe
def init_tts():
    global tts_engine
    if not hasattr(app, 'tts_engine'):
        app.tts_engine = pyttsx3.init()
    return app.tts_engine

# Store reminders in a thread-safe way
app.reminders = []
app.recurring_reminders = []

def drop_message(message):
    print("\n" + "=" * 40)
    print(f"REMINDER: {message}")
    print("=" * 40 + "\n")
    engine = init_tts()
    engine.say(f"Reminder: {message}")
    engine.runAndWait()



@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(path):
        return send_from_directory('.', path)
    return app.send_static_file(path)

# Your existing route handlers remain mostly the same
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_weather", methods=["POST"])
def weather():
    city = request.form["city"]
    weather_info = get_weather(city)
    return jsonify({"weather": weather_info})

@app.route("/set_reminder", methods=["POST"])
def set_reminder_route():
    try:
        data = request.json
        if not data or 'input_text' not in data:
            return jsonify({'status': 'error', 'message': 'Invalid input'}), 400
        
        input_text = data['input_text']
        response = set_reminder(input_text)
        return jsonify({'status': 'success', 'message': response})
    except Exception as e:
        app.logger.error(f"Error in set_reminder_route: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route("/schedule_meeting", methods=["POST"])
def schedule_meeting():
    try:
        if not request.is_json:
            return jsonify({
                'status': 'error', 
                'message': 'Content-Type must be application/json'
            }), 415

        data = request.get_json()
        if not data or 'command' not in data:
            return jsonify({
                'status': 'error', 
                'message': 'Invalid input: command is required'
            }), 400

        command = data['command']
        parse_result = parse_command(command)
        
        if parse_result is None:
            return jsonify({
                'status': 'error',
                'message': 'Could not parse meeting command'
            }), 400
            
        if not isinstance(parse_result, tuple) or len(parse_result) != 2:
            return jsonify({
                'status': 'error',
                'message': 'Invalid parse_command result format'
            }), 500
            
        summary, start_time = parse_result
        
        if not summary or not start_time:
            return jsonify({
                'status': 'error',
                'message': 'Invalid meeting summary or start time'
            }), 400
        
        end_time = start_time + timedelta(hours=1)
        india_tz = timezone('Asia/Kolkata')
        
        try:
            if start_time.tzinfo is None:
                start_time = india_tz.localize(start_time)
            if end_time.tzinfo is None:
                end_time = india_tz.localize(end_time)
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error processing timezone: {str(e)}'
            }), 500
        
        try:
            success, message = create_event(
                start_time=start_time,
                end_time=end_time,
                summary=summary,
                description=data.get('description'),
                location=data.get('location')
            )
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error creating calendar event: {str(e)}'
            }), 500
        
        if success:
            return jsonify({
                'status': 'success',
                'message': message,
                'meeting': {
                    'summary': summary,
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'description': data.get('description'),
                    'location': data.get('location')
                }
            })
        else:
            return jsonify({
                'status': 'error', 
                'message': message
            }), 500
            
    except ValueError as e:
        return jsonify({
            'status': 'error', 
            'message': f'Invalid input: {str(e)}'
        }), 400
    except Exception as e:
        app.logger.error(f"Error in schedule_meeting: {str(e)}")
        return jsonify({
            'status': 'error', 
            'message': f'Server error: {str(e)}'
        }), 500

def run_flask_app():
    app.run(debug=True)

if __name__ == "__main__":
    # Start the reminder checking thread
    reminder_thread = threading.Thread(target=check_reminders, daemon=True)
    reminder_thread.start()
    
    app.run(debug=True)

   