import source.utility.screen
import cv2 

'''these values are for a screen of 1920x1080'''
orange = {
    "x":528,
    "y":217
}

def get_orange_pixel():
    x,y = orange["x"],orange["y"]
    roi = source.utility.screen.get_screen_roi(int(x),int(y),1,1)
    hsv = cv2.cvtColor(roi,cv2.COLOR_BGR2HSV)
    print(f"{hsv[0, 0]} -> these colours should be put into xxxxxx location in xxxx file") 
    return hsv[0, 0]


if __name__ == "__main__":
    get_orange_pixel()
    input(f"")
