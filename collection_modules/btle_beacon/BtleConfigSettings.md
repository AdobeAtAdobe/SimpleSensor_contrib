## BTLE proximity module config settings
The config settings are in config/collectionPoint.conf  
This file is used by the RFID project and the BTLE project so you will see settings for both in the file 

Config Settings|||
--- | --- | --- 
**Property** | **Type** | **Description**  
collection_point_id | string | our name for the device with no special chars or spaces.  This needs to match the name defined in the collectionPoint id in the Creeper Controller server  
gateway_type | string | proximity by default.  this has the best testing and support.  This means someone is within range.  It will send an event out when someone passes into range as defined by BtleRssiClientInThreshold setting and will continue to send out an event every ProximityEventIntervalInMilliseconds (default 5 sec).  When a user leaves the in range an out event will be thrown until BtleRssiClientInThresholdType is exceeded.  In the default case of rssi that means when the users signal strengh is goes outside the BtleRssiClientInThreshold and we count them as missing for BtleClientOutCountThreshold number or leave_time has exceeded we throw an out event. The other gate types are IN,OUT,INOUT.  They have not been used in production but they are used as to throw event in a gate type use case.  So IN throws one event when the BTLE is seen.  OUT throws an out when the user is seen,  and INOUT throws one IN message the first time the user is seen and one OUT for the next time the user is seen.  Example use case would be one BTLE at a IN door and another at an exit door.  
leave_time | integer | if the user has not been in range for this time they are considered not in range   abandoned_client_cleanup_interval | string | this is a scheduled time that we run a check for any super old clients left abandoned in the system  
abandoned_client_cleanup_interval | integer | We run cleanup to pull out clients we are tracking that had never reported out of range and just disappear on us
abandoned_client_timeout | integer | this is the max time last seen that we use when doing our abandoned_client_cleanup_interval clean up
btle_test_mode | boolean | outputs a ton of data to the console in big pretty easy to read 
cec_data | boolean | adds in Adobe CEC related data to the event. Used for an applciation at Adobe
eventmanager_debug | boolean | this flag allows more output related to the event manager to be shown in the DEBUG log
show_client_range_debug | boolean | This setting is handy when your trying to setup the collection point and find the right value to set your btle_rssi_client_in_threshold value to
btle_rssi_client_in_threshold | integer | upper end of signal strength where we consider the user in.  IG -68 (about 6 meters) anything closer with stronger signal will be considered in range -65, -50, -44, etc and -78 would be OUT.  Use this to tune your distance IF the BtleRssiClientInThresholdType is set to rssi.  If BtleRssiClientInThresholdType is set to distance this will a number like 5 indicating max meters.  Distance is not good at this time I would stick to rssi
btle_rssi_client_in_threshold_type | string | rssi for keying off signal strength or distance which is a calculation of signal strength and broadcast power to figure distance.  I would use rssi, distance was not perfect yet.
proximity_event_interval | integer | how often we will send out a message letting clients know the user is in the area.  IG 5000 will send a client in every 5 seconds
btle_device_id | string |  comport id or device path in osx or linux where device can be found
btle_advertising_major_min | integer | ibeacon major min number we care about. if your looking for one number only set this to that number.  
btle_advertising_major_max | integer | ibeacon major max number we care about. if your looking for one number only set this to that number.  
btle_advertising_minor_min | integer | ibeacon minor min value we care about when scanning for minors.  If your looking for only one minor, say 100, then set it to that number.
btle_advertising_minor_max | integer | ibeacon minor max value we care about when scanning for minors.  If your looking for only one minor, say 100, then set it to that number.
btle_anomaly_reset_limit | integer | if we see spikes and weird responses from a device we will reset after this limit has been seen clearing up their count of IN and OUTS
btle_rssi_needed_sample_size | integer | this is the number of IN RANGE in events we need to see before we send the IN event.  1 is a good number but in weird environments where there can be crazy spikes up and down you may need to adjust this.
btle_rssi_max_sample_size | string | this is the size of the sample we take before we consider user in range.  I would leave this at 1
btle_rssi_error_variance | float | we use this to detect what we consider an anomaly in the signal
btle_device_baud_rate | string | sevice read baud rate
btle_device_tx_power| string | btle device transmit power.  sets the device output power
btle_client_out_count_threshold | string |  how many times a user needs to be seen out of range before we send the out event
slack_channel_webhook_url | string |  we use this to warn us if the service fails to connect to the BTLE reader when started.  We have people watching for messages there and responding in emergencies


### quick config
Change btle_device_id, btle_advertising_major_min, btle_advertising_major_max, BtleAdvertisibtle_advertising_minor_min, btle_advertising_minor_max then run it.  Then I would work on tuning btle_rssi_client_in_threshold by watching console output and having someone walk in and out of range and watching the rssi value reported.  Tune the value and restart until you get the right value to register when the user is in the right area. 
