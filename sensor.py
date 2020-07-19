"""Support for RATP transporteur public de Paris."""
from datetime import timedelta
import logging

from requests import get, HTTPError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, TIME_MINUTES
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by RATP & Rest API from Pierre Grimaud"

ICON_BUS   = "mdi:bus-clock"
ICON_METRO = "mdi:clock-end"

#CONF_APP_ID = "app_id"
#CONF_APP_KEY = "app_key"

CONF_TYPE = "type"
CONF_LINE = "line"
CONF_SLUGNAME = "name"
CONF_DIRECTION = "direction"

CONF_STOPS = "stops"

TYPE_BUS = "bus"
TYPE_METRO = "metro"

ATTR_STOP = "stop"
ATTR_LINE = "line"
ATTR_DIRECTION = "direction"
ATTR_NEXT = "next"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

LINE_STOP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE): cv.string,
        vol.Required(CONF_SLUGNAME): cv.string,
        vol.Required(CONF_LINE): cv.string,
        vol.Required(CONF_DIRECTION): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOPS): vol.All(cv.ensure_list, [LINE_STOP_SCHEMA]),
    }
)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensors."""

    sensors = []

    for line_stop in config.get(CONF_STOPS):
        type = line_stop[CONF_TYPE]
        line = line_stop[CONF_LINE]
        stop = line_stop[CONF_SLUGNAME]
        direction = line_stop[CONF_DIRECTION]
        if line_stop.get(CONF_NAME):
            name = f"{line} - {line_stop[CONF_NAME]} ({stop})"
        else:
            name = f"{line} - {stop}"
        
        sensors.append(IDFMSensor( stop, type, line, direction, name))

    add_entities(sensors, True)


class IDFMSensor(Entity):
    """Implementation of a IDFM line/stop Sensor."""

    def __init__(self, type, stop, line, direction, name):
        """Initialize the sensor."""
        self._type = type
        self._stop = stop
        self._line = line
        self._direction = direction
        self._name = name
        self._unit = TIME_MINUTES
        self._state = None
        self._next = None

        if type == TYPE_BUS:
            url_type = "buses"
        elif type == TYPE_METRO:
            url_type = "metros"

        self._url = f"https://api-ratp.pierre-grimaud.fr/v4/schedules/{url_type}/{line}/{stop}/{direction}"
        
    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        if type == TYPE_BUS:
          return ICON_BUS
        else:
          return ICON_METRO

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return f"{self._stop}_{self._line}_{self._direction}"

    @property
    def state(self):
        """Return the next departure time."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the last update."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STOP: self._stop,
            ATTR_LINE: self._line,
            ATTR_DIRECTION: self._direction,
            ATTR_NEXT: self._next,
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the next information."""
        try:
            headers = {'accept': 'application/json'}
            r = get(self._url, headers)
            schedule = r.json()

            depart = {}
            for departure in range(2):
                if schedule['result']['schedules'][departure]['message'] == "A l'arret":
                    depart[departure] = 0
                else:
                    depart[departure] = int(schedule['result']['schedules'][departure]['message'][:-2])

                self._state = depart[0]
                self._next = depart[1]

        except HTTPError:
            _LOGGER.error(
                "Unable to fetch data from IDFM API."
            )