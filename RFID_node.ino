#include <SPI.h>
#include <ESP8266HTTPClient.h>
#include <ESP8266WiFi.h>
#include <deprecated.h>
#include <MFRC522.h>
#include <MFRC522Extended.h>
#include <require_cpp11.h>

/*************************************************************************************/
/*******************************Adjustable Parameters********************************/
/************************************************************************************/

const char* ssid     = "D3@D70CK";
const char* password = "T!T@N_01";
const char* userName = "room1_PIR_1";
const int clusterID=1;
const char* server="10.10.0.4";


/*************************************************************************************/
/*************************************************************************************/
#define rs_pin 5
#define ss_pin 15
#define m_sensor 0
MFRC522 reader(ss_pin, rs_pin);
int PIR_val = 0,flag=0,sensor_state;

void setup() {
  //Serial.begin(115200);
  delay(500);
  SPI.begin();
  reader.PCD_Init();

  /*WIFI set-up*/
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    //Serial.print(".");
  }
 // pinMode(LED_BUILTIN,OUTPUT); //set Builtin NodeMCU LED as OUTPUT
  pinMode(m_sensor,INPUT); //Motion Sensor to Pin D7(13)
}
/***********
 * Stub to Post daLta to server
***********/
void post_data(String data){
  HTTPClient http;
  
  http.begin("http://"+(String)server+"/IOT/insert_data.php");
  http.addHeader("Content-Type","application/x-www-form-urlencoded");
  int httpCode=http.POST(data);
  String payload=http.getString();
  http.end();
  
}
void loop() {
  sensor_state=digitalRead(m_sensor);
  if(sensor_state==HIGH){
  delay(1000);
  /*************************************************************************************/
  /*************************************************************************************/
  
  if ( ! reader.PICC_IsNewCardPresent())
  {
    return;
  }
  // Select one of the cards
  if ( ! reader.PICC_ReadCardSerial())
  {
    Serial.println("No new serial");
    return;
  }
  //Serial.print("UID tag :");
  String content = "";
  byte letter;
  for (byte i = 0; i < reader.uid.size; i++)
  {
    //Serial.print(reader.uid.uidByte[i] < 0x10 ? " 0" : " ");
   //Serial.print(reader.uid.uidByte[i], HEX);
    content.concat(String(reader.uid.uidByte[i] < 0x10 ? " 0" : ""));
    content.concat(String(reader.uid.uidByte[i], HEX));
  }
  Serial.println();
  Serial.print("ID : ");
  content.toUpperCase();
  Serial.println(content.substring(1));
/*************************************************************************************/
/*************************************************************************************/
delay(500);
  
  
   if(flag==0){
      String data= "user_name=" + (String) userName +"&cluster_id="+ (String) clusterID +"&device_DATA=activated&sensor=true&id="+content.substring(1);
      //Serial.println(data);
      post_data(data);
      flag++;
    }
    digitalWrite(LED_BUILTIN,LOW);
    //Serial.println("Motion Detected on Outer Sensor!!");
     delay(2500);
    flag=0;
    digitalWrite(LED_BUILTIN,HIGH);
  }

}



