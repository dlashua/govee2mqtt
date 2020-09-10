
Govee recently released a public API to control their WiFi light strips, among other things.

I've created govee2mqtt (with homeassistant discovery) to integrate these devices.

This is very early code with little documentation. However, if you're interested, please give it a spin and feel free to submit PRs to help finish the feature set.

A few notes:
* Govee's API is SLOW. Not only does each request take longer than it should, it takes, sometimes, 3 to 4 seconds for the command to reach the light strip. Hopefully, they'll speed this up as time goes on.
* I only have model H6159. I've not tested with anything else though, in theory, it should work.
* Support is there for power on/off, brightness, and rgb_color. White Temperature is next in my list.
* Dockerfile is coming soon.

# Getting Started

```bash
git clone https://github.com/dlashua/govee2mqtt.git
cd govee2mqtt
pip3 install -r ./requirements.txt
cp config.yaml.sample config.yaml
vi config.yaml
python3 ./app.py -c ./
```

# Getting an API KEY
* Open the Govee App
* Tap on the "profile" icon (bottom right)
* Tap on "about us"
* Tap on "Apply for API Key"
* Get the API key via email within minutes
