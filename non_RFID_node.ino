#include <ESP8266HTTPClient.h>
#include <ESP8266WiFi.h>


/**
 * Node and Access Point Setup Code.
 */
const char* ssid     = "D3@D70CK";
const char* password = "T!T@N_01";
const char* userName = "room1_PIR_1";
const int clusterID=1;
const char* server="10.10.0.4";

/*********************************/



/*
 * ############CRITICAL CODE DO NOT TOUCH############
*/
 int m_sensor=0;
void setup() {
  //Serial.begin(115200);
  delay(10);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    //Serial.print(".");
  }
  //Serial.println("connected to"+(String)ssid);  
  //Serial.println("IP address: ");
  //Serial.println(WiFi.localIP());
  
  pinMode(LED_BUILTIN,OUTPUT); //set Builtin NodeMCU LED as OUTPUT
  pinMode(m_sensor,INPUT); //Motion Sensor to Pin D7(13)
}
void post_data(String data){
  HTTPClient http;
  
  http.begin("http://"+(String)server+"/IOT/insert_data.php");
  http.addHeader("Content-Type","application/x-www-form-urlencoded");
  int httpCode=http.POST(data);
  String payload=http.getString();
  http.end();
  
}
int flag=0;
int sensor_state;
void loop() {
  sensor_state=digitalRead(m_sensor);
  if(sensor_state==HIGH){
   if(flag==0){
      String data= "user_name=" + (String) userName +"&cluster_id="+ (String) clusterID +"&device_DATA=activated&sensor=true";
      
      post_data(data);
      flag++;
    }
    digitalWrite(LED_BUILTIN,LOW);
    //Serial.println("Motion Detected on Outer Sensor!!");
     delay(2500);
    flag=0;
  }else{
    digitalWrite(LED_BUILTIN,HIGH);
    //Serial.println("No Motion!");
  delay(500);
  }
}
/*
 * *********************************************************************
 * *********************************************************************
*/

