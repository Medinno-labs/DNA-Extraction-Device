from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time
import threading
import RPi.GPIO as GPIO
import csv
import os
import spidev
import board
import busio
import adafruit_mlx90614


# Initialize I2C
i2c = busio.I2C(board.SCL, board.SDA)

# Connect to the MLX90614 sensor
mlx1 = adafruit_mlx90614.MLX90614(i2c , address = 0x5A)
mlx2 = adafruit_mlx90614.MLX90614(i2c , address = 0x5B)




# Flask and SocketIO setup
app = Flask(__name__)
socketio = SocketIO(app)

# CSV setup
csv_filename = "Extraction_Device.csv"
file_exists = os.path.isfile(csv_filename)
if not file_exists:
    with open(csv_filename, mode='w', newline='') as file:
        csv_writer = csv.writer(file)
        csv_writer.writerow(["Elapsed Time (s)", "Extraction Device TEMP 1 (°C)" ,"Extraction Device TEMP 2 (°C)"])

running = False  # Flag to control thread


def read_temp():
   global mlx1,mlx2
   object_temp_1 = mlx1.object_temperature
   object_temp_2 = mlx2.object_temperature
   return round(object_temp_1,2) , round(object_temp_2,2)



def generate_temperature_data():
    global running

    start_time = time.time()
    while running:
        elapsed_time = round(time.time() - start_time, 2)
        temp1 , temp2 = read_temp()

        # Send to front-end
        socketio.emit('update', {
            "elapsed_time": elapsed_time,
            "temp1": temp1,
            "temp2": temp2
        })

        # Append to CSV
        with open(csv_filename, mode='a', newline='') as file:
            csv_writer = csv.writer(file)
            csv_writer.writerow([elapsed_time, temp1 , temp2])

        time.sleep(1)

@app.route('/')
def index():
    return render_template('2_sensor.html')

@app.route('/start', methods=['POST'])
def start_experiment():
    global running
    if not running:
        running = True
        threading.Thread(target=generate_temperature_data, daemon=True).start()
    return "Experiment Started", 200

@app.route('/stop', methods=['POST'])
def stop_experiment():
    global running
    running = False
    return "Experiment Stopped", 200

if __name__ == '__main__':
    try:
        socketio.run(app, debug=True, host='0.0.0.0', port=5001, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("Shutting down.")
    finally:
        i2c.deinit()
