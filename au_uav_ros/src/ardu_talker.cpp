#include "au_uav_ros/ardu_talker.h"
#include <cstdio> //printf
#include <string>
#include <ros/console.h>	//used for debugging

au_uav_ros::ArduTalker::ArduTalker()	{
	m_port = "dev/ttyACM0";
	m_baud = 115200;
}

au_uav_ros::ArduTalker::ArduTalker(std::string _port, int _baud)	{
	m_port = _port;
	m_baud = _baud;	
	
}

bool au_uav_ros::ArduTalker::init(ros::NodeHandle _n)	{
	//Open and setup port.
	if(m_ardu.open_port(m_port) == -1)	{
		ROS_INFO("Could not open port %s", m_port.c_str());
		return false;
	}
	else	{
		ROS_INFO("opened port %s", m_port.c_str());
		m_ardu.setup_port(m_baud, 8, 1, true);		
	}

	//mavlink
	sysid = -1;
	compid = 110;	//not entirely sure why this is 110
	serial_compid =0;	//the compid that the GCS is getting from plane (so we won't need)
	pc2serial = true;
	updateIndex = 0;
	WPSendSeqNum = 0;

	//Set up Ros stuff. Todo - 
	m_node = _n;
	m_command_sub = m_node.subscribe("ca_command", 10, &ArduTalker::commandCallback, this); 
	
	m_telem_pub = m_node.advertise<au_uav_ros::Telemetry>("all_telemetry", 5);
	m_mav_telem_pub = m_node.advertise<au_uav_ros::Telemetry>("my_mav_telemetry", 5);//the type will need to change
	return true;
}

void au_uav_ros::ArduTalker::run()	{
	ROS_INFO("Entering Run");

	//Spin up thread to execute myTelemCallback()
	boost::thread sendCommands(boost::bind(&ArduTalker::spinThread, this));	

	//Start listening for telemetry and commands, upon receiving proper command
	//from ground station, execute shutdown and join
	listen();

	ros::shutdown();
	sendCommands.join();	
}

void au_uav_ros::ArduTalker::shutdown()	{
	//ROS_INFO("Shutting down Xbee port %s", m_port.c_str());
	printf("ArduTalker::Shutting down Xbee port %s\n", m_port.c_str()); //i ros::shutdown when exiting run
	m_ardu.close_port();
}

//Input - listening ardu for other telem msgs and gcs commands
//---------------------------------------------------------------------------

void au_uav_ros::ArduTalker::listen()	{
	while(ros::ok())
	{
		//get a mavlink message from the serial line
		mavlink_message_t message = au_uav_ros::mav::readMavlinkFromSerial(m_ardu);
		//decode the message and post it to the appropriate topic
		if(message.msgid == MAVLINK_MSG_ID_HEARTBEAT)
		{
			mavlink_heartbeat_t receivedHeartbeat;
			mavlink_msg_heartbeat_decode(&message, &receivedHeartbeat);
			ROS_INFO("Received heartbeat");
		}
		if(message.msgid == MAVLINK_MSG_ID_AU_UAV)
		{
			//ROS_INFO("Received AU_UAV message from serial with ID #%d (sys:%d|comp:%d):\n", message.msgid, message.
			au_uav_ros::Telemetry tUpdate;
			mavlink_au_uav_t myMSG;
			mavlink_msg_au_uav_decode(&message, &myMSG);            // decode generic mavlink message in$
			au_uav_ros::mav::convertMavlinkTelemetryToROS(myMSG, tUpdate);                   // decode AU_UAV mavlink str$
			tUpdate.planeID = message.sysid;                                // update planeID
	  		m_telem_pub.publish(tUpdate);
		        ROS_INFO("Received telemetry message from UAV[#%d] (lat:%f|lng:%f|alt:%f)", tUpdate.planeID, tUpdate.currentLatitude, tUpdate.currentLongitude, tUpdate.currentAltitude);
		}
	}
}



//Output - writing to xbee
//---------------------------------------------------------------------------
void au_uav_ros::ArduTalker::commandCallback(au_uav_ros::Command cmd)	{
	ROS_INFO("ArduTalker::commandCallback::ding! \n");
	//----------------
	//Callback time! 
	//----------------
	mavlink_message_t mavlinkMsg;
	sysid = cmd.planeID;
	//stuff mavlinkMsg with the correct paramaters
	mavlink_msg_mission_item_pack(sysid, compid, &mavlinkMsg, 
			              sysid, serial_compid, 0, 
				      MAV_FRAME_GLOBAL, MAV_CMD_NAV_WAYPOINT, 
				      2, 0, 20.0, 100.0, 1.0, 0.0, 
				      cmd.latitude, cmd.longitude, cmd.altitude);

	//take command -> send to ardupilot	
	static uint8_t buffer[MAVLINK_MAX_PACKET_LEN];
	int messageLength = mavlink_msg_to_send_buffer(buffer, &mavlinkMsg);
	m_ardu.lock();
	int written = write(m_ardu.getFD(), (char*)buffer, messageLength);
	m_ardu.unlock();
	if (messageLength != written) ROS_ERROR("ERROR: Wrote %d bytes but should have written %d\n",
						written, messageLength);
}

void au_uav_ros::ArduTalker::spinThread()	{
	ROS_INFO("ArduTalker::spinThread::Starting spinner thread");
	//Handle myTelemCallback()
	ros::spin();	
}

int main(int argc, char** argv)	{

	std::cout << "hello world!" <<std::endl;
	std::string port = "/dev/ttyACM0";

	ros::init(argc, argv, "ArduTalker");
	ros::NodeHandle n;
	au_uav_ros::ArduTalker talk(port, 115200);
	if(talk.init(n))	//OK. what if the xbee can't be read???
		talk.run();
	talk.shutdown();
}
