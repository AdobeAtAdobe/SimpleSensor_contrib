# SimpleSensor_contrib
## Repository for SimpleSensor's BTLE proximity module
What is a BTLE proximity module?  This SimpleSensor module uses BlueTooth scanning to locate Bluetooth beacons within a certian range of the scanning point.   

This was built and tuned for the BlueGiga bled112 device.  It has been used with other BTLE hardware devices as well. 

## Table of Contents

  * [Example Usage](#example-usage-types "Example usage")
  * [Configuration Settings](./BtleConfigSettings.md "BTLE Configuration settings")

### Example usage types

#### Example Proximity Gateway:  
- Person or thing wearing a bluetooth beacon is within 10m of scanner and event is thrown.    
- Then ever 3 seconds the beacon is seen within 10m a follow up event is thrown.  
- When the beacon has not been seen for 20 scans a exit event is thrown.

#### Proximity Gateway Events thrown
ClientIn
ClientOut

ClientIn will be sent after the ibeacon is seen closer than the value listed in CONFIG value BtleRssiClientInThreshold
after the user is IN RANGE you will continue to get events at an interval specified by CONFIG value ProximityEventIntervalInMilliseconds.  So if this is set to 5 seconds you will get a ClientIn every 5 seconds to let you know the user is still found and within range.

ClientOut will be send after the ibeacon is seen with a strenght higher than the range found in CONFIG BtleRssiClientInThreshold.  They must be seen out of range for CONFIG leaveTimeInMilliseconds before the event is sent.  This is to help to smooth out the events and is needed especially when the users are right on the edge of the max range of the area defined as in range.

ClientOut will also be send when old clients are cleaned up.  This handles when people don't smoothly move out of range but instead disapear from the reader.  This clean up is defined by AbandonedClientCleanupIntervalInMilliseconds


#### Example In gateway:
- Person or thing wearing a bluetooth beacon is within 10m of scanner and IN event is thrown.  
- No event is thrown when beason leaves the scan area

#### Example Out gateway:
- Person or thing wearing a bluetooth beacon is within 10m of scanner and OUT event is thrown
- No event is thrown when beason leaves the scan area

#### Example In/Out gateway:
- Person or thing wearing a bluetooth beacon is within 10m of scanner and IN event is thrown if its the first time we have seen the user
- After the beacon leaves the scan area then is seen again an OUT event is thrown

