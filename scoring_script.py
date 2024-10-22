import cv2 as cv
import cv2.aruco as aruco
import numpy as np
import math
import requests
import json
import time

#
# calibration_data = np.load('calibration_params.npz')
# mtx = calibration_data['mtx']
# dist = calibration_data['dist']

# cap = cv.VideoCapture(1)
aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
parameters = aruco.DetectorParameters()
prev_frame = None
fps_limit = 1
start_time = time.time()
score = {10: [], 9: [], 8: [], 7: [], 6: [], 5: [], 4: [], 3: [], 2: [], 1: []}
angles = {10: [], 9: [], 8: [], 7: [], 6: [], 5: [], 4: [], 3: [], 2: [], 1: []}
score_sum = 0
URL = 'http://127.0.0.1:5000/api/score'


# Initialize the video feed

def selected_ip():
    try:
        response = requests.get('http://127.0.0.1:5000/api/selected_ip')  # Flask endpoint
        if response.status_code == 200:
            return response.json().get('selected_ip')
        else:
            print("Error fetching selected IP")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

selected_ip =  selected_ip()  # Fetch selected IP from the Flask app

if selected_ip is None:
    raise ValueError("No selected IP provided. Please ensure you have selected the device in the app.")

# Use the selected IP in the video stream
cap = cv.VideoCapture(f"http://{selected_ip}:8000/video_feed")  # Use dynamic IP address

def getArucoCenters(corners):
    print("getArucoCenters: Processing Aruco corners")
    centers = []
    for marker in corners:
        x_sum = 0
        y_sum = 0
        for x, y in marker[0]:
            x_sum += x
            y_sum += y

        center = (int(x_sum // 4), int(y_sum // 4))
        centers.append(center)
    print(f"getArucoCenters: Centers calculated: {centers}")
    return centers


def addToDict(centers, ids):
    print(f"addToDict: Adding centers to dict with IDs: {ids}")
    center_dict = {}
    for i in range(len(centers)):
        center_dict[ids[i][0]] = centers[i]

    print(f"addToDict: Center dict: {center_dict}")
    return center_dict


def correctPerspective(frame):
    print("correctPerspective: Converting frame to grayscale and detecting Aruco markers")
    gray_frame = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
    corners, ids, rejected = aruco.detectMarkers(image=gray_frame, dictionary=aruco_dict, parameters=parameters)
    markers_found = False
    if ids is not None and len(ids) == 4:
        print(f"correctPerspective: Aruco markers detected with IDs: {ids}")
        centers = getArucoCenters(corners)
        center_dict = addToDict(centers, ids)
        points_src = np.array([center_dict[0], center_dict[3], center_dict[1], center_dict[2]])
        points_dst = np.float32([[0, 0], [0, 500], [500, 0], [500, 500]])

        matrix, _ = cv.findHomography(points_src, points_dst)
        image_out = cv.warpPerspective(frame, matrix, (500, 500))
        frame = image_out
        markers_found = True
    else:
        print("correctPerspective: No valid Aruco markers found")

    return frame, markers_found


def getBullets(th1, output_frame, draw=True):
    print("getBullets: Detecting bullets from contours")
    contours = cv.findContours(th1, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)[0]
    bullets = []
    for contour in contours:
        approx = cv.approxPolyDP(contour, 0.02 * cv.arcLength(contour, True), True)
        ((x, y), radius) = cv.minEnclosingCircle(contour)
        bullets.append((int(x), int(y)))
        if draw:
            cv.circle(output_frame, (int(x), int(y)), (int(radius)), (0, 0, 255), -1)

    print(f"getBullets: Bullets detected: {bullets}")
    return bullets


def calculateDistance(x1, y1, x2=251, y2=287):
    radius = math.sqrt((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1))
    print(f"calculateDistance: Distance calculated between ({x1}, {y1}) and ({x2}, {y2}) is {radius}")
    return radius


def updateScore(bullets):
    global score_sum, score, angles

    print(f"updateScore: Updating score with bullets: {bullets}")
    for x, y in bullets:
        dist = calculateDistance(x, y)
        angle = calculateAngle(x, y)
        if 0 <= dist <= 12:
            score[10].append((x, y))
            score_sum += 10
            angles['10'].append(angle)
        elif 12 < dist <= 36:
            score[9].append((x, y))
            score_sum += 9
            angles['9'].append(angle)
        elif 36 < dist <= 60:
            score[8].append((x, y))
            score_sum += 8
            angles['8'].append(angle)
        elif 60 < dist <= 84:
            score[7].append((x, y))
            score_sum += 7
            angles['7'].append(angle)
        elif 84 < dist <= 108:
            score[6].append((x, y))
            score_sum += 6
            angles['6'].append(angle)
        elif 108 < dist <= 132:
            score[5].append((x, y))
            score_sum += 5
            angles['5'].append(angle)
        elif 132 < dist <= 156:
            score[4].append((x, y))
            score_sum += 4
            angles['4'].append(angle)
        elif 156 < dist <= 180:
            score[3].append((x, y))
            score_sum += 3
            angles['3'].append(angle)
        elif 180 < dist <= 204:
            score[2].append((x, y))
            score_sum += 2
            angles['2'].append(angle)
        elif 204 < dist <= 228:
            score[1].append((x, y))
            score_sum += 1
            angles['1'].append(angle)

    print(f"updateScore: Updated score: {score}, score_sum: {score_sum}")


def drawFrame(frame):
    print("drawFrame: Drawing score on frame")
    i = 1
    for points in score.keys():
        frame = cv.putText(frame, f"{points}:{len(score[points])}", (0, 20 * i), cv.FONT_HERSHEY_COMPLEX, 0.5,
                           (0, 0, 255), 2)
        i += 1
    return frame


def sendData(image, angles):
    print("sendData: Sending data to server")
    _, img_encoded = cv.imencode('.jpg', image)
    files = {'image': img_encoded.tobytes(),
             'angles': (None, json.dumps(angles), 'application/json')}
    try:
        response = requests.post(URL, files=files)
        print(f"sendData: Response from server: {response.status_code}, {response.text}")
        return response
    except Exception as e:
        print(f"sendData: Error sending data: {e}")
        return None


def calculateAngle(x, y):
    delta_x = (x - 251)
    delta_y = (y - 287)
    if delta_x == 0:
        angle = -90
    else:
        angle = round(math.atan2(delta_y, delta_x) * 180 / math.pi)
    print(f"calculateAngle: Angle calculated: {angle} for point ({x}, {y})")
    return angle


def get_current_score():
    print("get_current_score: Fetching current score from server")
    try:
        response = requests.get('http://127.0.0.1:5000/api/data')
        if response.status_code == 200:
            print("get_current_score: Score data fetched successfully")
            return response.json().get('angles')
        else:
            print(f"get_current_score: Error fetching score, status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"get_current_score: Error: {e}")
        return None


angles = get_current_score()
print(f"Initial angles: {angles}")
if angles is None:
    angles = {10: [], 9: [], 8: [], 7: [], 6: [], 5: [], 4: [], 3: [], 2: [], 1: []}
for val in angles.keys():
    score_sum += int(val) * len(angles[val])

while True:
    ret, frame = cap.read()
    # frame = cv.undistort(frame, mtx, dist, None)
    if not ret:
        print("Error with Webcam")
        break

    curr_time = time.time()
    if ((curr_time - start_time)) > fps_limit:
        corrected_image, target_detected = correctPerspective(frame)
        frame = corrected_image.copy()

        frame = cv.GaussianBlur(frame, (5, 5), 0)
        output_frame = frame.copy()

        if target_detected:
            if prev_frame is not None:
                diff = cv.absdiff(prev_frame, frame)
                gray = cv.cvtColor(diff, cv.COLOR_BGR2GRAY)
                blur = cv.GaussianBlur(gray, (5, 5), 0)
                _, th1 = cv.threshold(blur, 50, 255, cv.THRESH_BINARY)

                bullets = getBullets(th1, output_frame)
                updateScore(bullets)

            prev_frame = frame
            frame = drawFrame(output_frame)

        start_time = time.time()

    # cv.imshow("Frame", frame)

    if cv.waitKey(1) & 0xFF == ord('q'):
        print("Exit signal received, closing the application.")
        break

sendData(frame, angles)
cap.release()
cv.destroyAllWindows()
