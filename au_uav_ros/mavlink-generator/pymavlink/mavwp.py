'''
module for loading/saving waypoints
'''

import os
import mavutil, time


class MAVWPError(Exception):
        '''MAVLink WP error class'''
        def __init__(self, msg):
            Exception.__init__(self, msg)
            self.message = msg

class MAVWPLoader(object):
    '''MAVLink waypoint loader'''
    def __init__(self, target_system=0, target_component=0):
        self.wpoints = []
        self.target_system = target_system
        self.target_component = target_component
	self.last_change = time.time()

    def count(self):
        '''return number of waypoints'''
        return len(self.wpoints)

    def wp(self, i):
        '''return a waypoint'''
        return self.wpoints[i]

    def add(self, w):
        '''add a waypoint'''
        w.seq = self.count()
        self.wpoints.append(w)
	self.last_change = time.time()

    def set(self, w, idx):
        '''set a waypoint'''
        w.seq = idx
        if w.seq == self.count():
            return self.add(w)
        if self.count() <= idx:
            raise MAVWPError('adding waypoint at idx=%u past end of list (count=%u)' % (idx, self.count()))
        self.wpoints[idx] = w
	self.last_change = time.time()

    def remove(self, w):
        '''remove a waypoint'''
        self.wpoints.remove(w)
	self.last_change = time.time()

    def clear(self):
        '''clear waypoint list'''
        self.wpoints = []
	self.last_change = time.time()

    def _read_waypoint_v100(self, line):
        '''read a version 100 waypoint'''
        cmdmap = {
            2 : mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            3 : mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
            4 : mavutil.mavlink.MAV_CMD_NAV_LAND,
            24: mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            26: mavutil.mavlink.MAV_CMD_NAV_LAND,
            25: mavutil.mavlink.MAV_CMD_NAV_WAYPOINT ,
            27: mavutil.mavlink.MAV_CMD_NAV_LOITER_UNLIM
            }
        a = line.split()
        if len(a) != 13:
            raise MAVWPError("invalid waypoint line with %u values" % len(a))
        if mavutil.mavlink10():
            fn = mavutil.mavlink.MAVLink_mission_item_message
        else:
            fn = mavutil.mavlink.MAVLink_waypoint_message
        w = fn(self.target_system, self.target_component,
               int(a[0]),    # seq
               int(a[1]),    # frame
               int(a[2]),    # action
               int(a[7]),    # current
               int(a[12]),   # autocontinue
               float(a[5]),  # param1,
               float(a[6]),  # param2,
               float(a[3]),  # param3
               float(a[4]),  # param4
               float(a[9]),  # x, latitude
               float(a[8]),  # y, longitude
               float(a[10])  # z
               )
        if not w.command in cmdmap:
            raise MAVWPError("Unknown v100 waypoint action %u" % w.command)
    
        w.command = cmdmap[w.command]
        return w

    def _read_waypoint_v110(self, line):
        '''read a version 110 waypoint'''
        a = line.split()
        if len(a) != 12:
            raise MAVWPError("invalid waypoint line with %u values" % len(a))
        if mavutil.mavlink10():
            fn = mavutil.mavlink.MAVLink_mission_item_message
        else:
            fn = mavutil.mavlink.MAVLink_waypoint_message
        w = fn(self.target_system, self.target_component,
               int(a[0]),    # seq
               int(a[2]),    # frame
               int(a[3]),    # command
               int(a[1]),    # current
               int(a[11]),   # autocontinue
               float(a[4]),  # param1,
               float(a[5]),  # param2,
               float(a[6]),  # param3
               float(a[7]),  # param4
               float(a[8]),  # x (latitude)
               float(a[9]),  # y (longitude)
               float(a[10])  # z (altitude)
               )
        return w


    def load(self, filename):
        '''load waypoints from a file.
        returns number of waypoints loaded'''
        f = open(filename, mode='r')
        version_line = f.readline().strip()
        if version_line == "QGC WPL 100":
            readfn = self._read_waypoint_v100
        elif version_line == "QGC WPL 110":
            readfn = self._read_waypoint_v110
        else:
            f.close()
            raise MAVWPError("Unsupported waypoint format '%s'" % version_line)

        self.clear()

        for line in f:
            if line.startswith('#'):
                continue
            line = line.strip()
            if not line:
                continue
            w = readfn(line)
            if w is not None:
                self.add(w)
        f.close()
        return len(self.wpoints)


    def save(self, filename):
        '''save waypoints to a file'''
        f = open(filename, mode='w')
        f.write("QGC WPL 110\n")
        for w in self.wpoints:
            f.write("%u\t%u\t%u\t%u\t%f\t%f\t%f\t%f\t%f\t%f\t%f\t%u\n" % (
                w.seq, w.current, w.frame, w.command,
                w.param1, w.param2, w.param3, w.param4,
                w.x, w.y, w.z, w.autocontinue))
        f.close()

    def polygon(self):
	    '''return a polygon for the waypoints'''
	    points = []
	    for w in self.wpoints:
		    if w.command in [mavutil.mavlink.MAV_CMD_NAV_WAYPOINT]:
			    points.append((w.x, w.y))
	    return points


class MAVFenceError(Exception):
        '''MAVLink fence error class'''
        def __init__(self, msg):
            Exception.__init__(self, msg)
            self.message = msg

class MAVFenceLoader(object):
    '''MAVLink geo-fence loader'''
    def __init__(self, target_system=0, target_component=0):
        self.points = []
        self.target_system = target_system
        self.target_component = target_component
	self.last_change = time.time()

    def count(self):
        '''return number of points'''
        return len(self.points)

    def point(self, i):
        '''return a point'''
        return self.points[i]

    def add(self, p):
        '''add a point'''
        self.points.append(p)
	self.last_change = time.time()

    def clear(self):
        '''clear point list'''
        self.points = []
	self.last_change = time.time()

    def load(self, filename):
        '''load points from a file.
        returns number of points loaded'''
        f = open(filename, mode='r')
        self.clear()
        for line in f:
            if line.startswith('#'):
                continue
            line = line.strip()
            if not line:
                continue
            a = line.split()
            if len(a) != 2:
                raise MAVFenceError("invalid fence point line: %s" % line)
            p = mavutil.mavlink.MAVLink_fence_point_message(self.target_system, self.target_component,
                                                            self.count(), 0, float(a[0]), float(a[1]))
            self.add(p)
        f.close()
        for i in range(self.count()):
            self.points[i].count = self.count()
        return len(self.points)


    def save(self, filename):
        '''save fence points to a file'''
        f = open(filename, mode='w')
        for p in self.points:
            f.write("%f\t%f\n" % (p.lat, p.lng))
        f.close()

    def polygon(self):
	    '''return a polygon for the fence'''
	    points = []
	    for fp in self.points[1:]:
		    points.append((fp.lat, fp.lng))
	    return points
    

