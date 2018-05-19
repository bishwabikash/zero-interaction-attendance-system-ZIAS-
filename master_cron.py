'''
    Run this Script as a cron job for the required frequency i.e hourly, every minute, every hour, etc
    see cron manual for setting up
    Proprietory code of Bishwa Bikash Das
'''

import mysql.connector

con = mysql.connector.connect(user='IOT_master', password='IOT_pass1234##', host='127.0.0.1', database='iot_data')
res_con = mysql.connector.connect(user='IOT_master', password='IOT_pass1234##', host='127.0.0.1', database='iot_data')
cursor = con.cursor()
res_curs = res_con.cursor()
res_con.autocommit = True

'''query = (
    "SELECT DISTINCT a.device_ID AS 'dev1', b.device_ID AS 'dev2',abs(timestampdiff(SECOND,a.time_stamp,b.time_stamp)) AS 'devdiff', b.time_stamp AS 'dev2_ts',a.time_stamp AS 'dev1_ts',a.cluster_ID AS 'cluster' FROM sensor_data a,sensor_data b WHERE abs(timestampdiff(SECOND,a.time_stamp,b.time_stamp)) <3 AND a.device_ID <> b.device_ID  AND a.time_stamp < b.time_stamp AND a.cluster_ID=b.cluster_ID ")  # and a.time_stamp>= Date_SUB(NOW(),INTERVAL 1 HOUR)")
'''
query = (
    "SELECT DISTINCT a.device_ID AS 'dev1',a.RFID + b.RFID AS 'RFID',a.time_stamp AS 'timestamp',a.cluster_ID AS 'cluster' FROM sensor_data a,sensor_data b WHERE abs(timestampdiff(SECOND,a.time_stamp,b.time_stamp)) <3 AND a.device_ID <> b.device_ID  AND a.time_stamp < b.time_stamp AND a.cluster_ID=b.cluster_ID")  # and a.time_stamp>= Date_SUB(NOW(),INTERVAL 1 HOUR)")

cursor.execute(query)

'''
 Iterate through all the columns satisfying the query and return the number of entries or exits in the past hour
'''
data_dict = {}
for (dev1, dev1_ta, timestamp, cluster, RFID) in cursor:
    if int(dev1[-1]) % 2 == 0:
        print("Print")
        data_dict[RFID] = {'cluster': cluster, 'status': 1}

    else:
        data_dict[RFID] = {'cluster': cluster, 'status': -1}

for key in data_dict.keys():
    query_upd = "INSERT INTO entry_log(student_name, RFID, room_value, status) VALUES ((SELECT stud_name FROM student WHERE student.RFID = '" + str(
        key) + "'), '" + str(key) + "', (SELECT DISTINCT room_value FROM user_devices WHERE cluster_ID=" + str(
        data_dict[key]['cluster']) + "), " + data_dict[key]['status'] + ")"
    res_curs.execute(query_upd)

    # print(data_dict[key])
    print(query_upd)
cursor.close()
res_curs.close()
res_con.close()
con.close()
