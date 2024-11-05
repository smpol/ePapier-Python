from lib.waveshare_epd import epd7in5_V2

epd = epd7in5_V2.EPD()

epd.init()
epd.Clear()
epd.sleep()
epd7in5_V2.epdconfig.module_exit(cleanup=True)
exit()