#!/usr/bin/env python

import sys
import os
import time
import random
from functools import partial
from syncobj import SyncObj, SyncObjConf, replicated, FAIL_REASON

class TestObj(SyncObj):

	def __init__(self, selfNodeAddr, otherNodeAddrs, compactionTest = 0, dumpFile = None):
		cfg = SyncObjConf(autoTick=False, commandsQueueSize=10000, appendEntriesUseBatch=False)
		if compactionTest:
			cfg.logCompactionMinEntries = compactionTest
			cfg.logCompactionMinTime = 0.1
			cfg.appendEntriesUseBatch = True
			cfg.fullDumpFile = dumpFile
		super(TestObj, self).__init__(selfNodeAddr, otherNodeAddrs, cfg)
		self.__counter = 0

	@replicated
	def addValue(self, value):
		self.__counter += value
		return self.__counter

	def getCounter(self):
		return self.__counter

def doTicks(objects, timeToTick, interval = 0.05):
	currTime = time.time()
	finishTime = currTime + timeToTick
	while currTime < finishTime:
		for o in objects:
			o._onTick(0.0)
		time.sleep(interval)
		currTime = time.time()

_g_nextAddress = 6000 + 60 * (int(time.time()) % 600)

def getNextAddr():
	global _g_nextAddress
	_g_nextAddress += 1
	return 'localhost:%d' % _g_nextAddress

def syncTwoObjects():

	random.seed(42)

	a = [getNextAddr(), getNextAddr()]

	o1 = TestObj(a[0], [a[1]])
	o2 = TestObj(a[1], [a[0]])
	objs = [o1, o2]
	doTicks(objs, 3.5)

	assert o1._getLeader() in a
	assert o1._getLeader() == o2._getLeader()

	o1.addValue(150)
	o2.addValue(200)

	doTicks(objs, 0.5)

	assert o1.getCounter() == 350
	assert o2.getCounter() == 350

def syncThreeObjectsLeaderFail():

	random.seed(12)

	a = [getNextAddr(), getNextAddr(), getNextAddr()]

	o1 = TestObj(a[0], [a[1], a[2]])
	o2 = TestObj(a[1], [a[2], a[0]])
	o3 = TestObj(a[2], [a[0], a[1]])
	objs = [o1, o2, o3]

	doTicks(objs, 3.5)

	assert o1._getLeader() in a
	assert o1._getLeader() == o2._getLeader()
	assert o1._getLeader() == o3._getLeader()

	o1.addValue(150)
	o2.addValue(200)

	doTicks(objs, 0.5)

	assert o3.getCounter() == 350

	prevLeader = o1._getLeader()

	newObjs = [o for o in objs if o._getSelfNodeAddr() != prevLeader]

	assert len(newObjs) == 2

	doTicks(newObjs, 3.5)
	assert newObjs[0]._getLeader() != prevLeader
	assert newObjs[0]._getLeader() in a
	assert newObjs[0]._getLeader() == newObjs[1]._getLeader()

	newObjs[1].addValue(50)

	doTicks(newObjs, 0.5)

	assert newObjs[0].getCounter() == 400

	doTicks(objs, 0.5)
	for o in objs:
		assert o.getCounter() == 400

def manyActionsLogCompaction():

	random.seed(42)

	a = [getNextAddr(), getNextAddr(), getNextAddr()]

	o1 = TestObj(a[0], [a[1], a[2]], compactionTest=100)
	o2 = TestObj(a[1], [a[2], a[0]], compactionTest=100)
	o3 = TestObj(a[2], [a[0], a[1]], compactionTest=100)
	objs = [o1, o2, o3]

	doTicks(objs, 3.5)

	assert o1._getLeader() in a
	assert o1._getLeader() == o2._getLeader()
	assert o1._getLeader() == o3._getLeader()

	for i in xrange(0, 500):
		o1.addValue(1)
		o2.addValue(1)

	doTicks(objs, 1.5)

	assert o1.getCounter() == 1000
	assert o2.getCounter() == 1000
	assert o3.getCounter() == 1000

	assert o1._getRaftLogSize() <= 100
	assert o2._getRaftLogSize() <= 100
	assert o3._getRaftLogSize() <= 100

	newObjs = [o1, o2]
	doTicks(newObjs, 3.5)

	for i in xrange(0, 500):
		o1.addValue(1)
		o2.addValue(1)

	doTicks(newObjs, 4.0)

	assert o1.getCounter() == 2000
	assert o2.getCounter() == 2000
	assert o3.getCounter() != 2000

	doTicks(objs, 3.5)

	assert o3.getCounter() == 2000

	assert o1._getRaftLogSize() <= 100
	assert o2._getRaftLogSize() <= 100
	assert o3._getRaftLogSize() <= 100

def onAddValue(res, err, info):
	assert res == 3
	assert err == FAIL_REASON.SUCCESS
	info['callback'] = True

def checkCallbacksSimple():

	random.seed(42)

	a = [getNextAddr(), getNextAddr(), getNextAddr()]

	o1 = TestObj(a[0], [a[1], a[2]])
	o2 = TestObj(a[1], [a[2], a[0]])
	o3 = TestObj(a[2], [a[0], a[1]])
	objs = [o1, o2, o3]

	doTicks(objs, 3.5)

	assert o1._getLeader() in a
	assert o1._getLeader() == o2._getLeader()
	assert o1._getLeader() == o3._getLeader()


	callbackInfo = {
		'callback': False
	}
	o1.addValue(3, callback=partial(onAddValue, info=callbackInfo))

	doTicks(objs, 0.5)

	assert o2.getCounter() == 3
	assert callbackInfo['callback'] == True

def removeFiles(files):
	for f in (files):
		try:
			os.remove(f)
		except:
			pass

def checkDumpToFile():
	removeFiles(['dump1.bin', 'dump2.bin'])

	random.seed(42)

	a = [getNextAddr(), getNextAddr()]

	o1 = TestObj(a[0], [a[1]], compactionTest=True, dumpFile = 'dump1.bin')
	o2 = TestObj(a[1], [a[0]], compactionTest=True, dumpFile = 'dump2.bin')
	objs = [o1, o2]
	doTicks(objs, 3.5)

	assert o1._getLeader() in a
	assert o1._getLeader() == o2._getLeader()

	o1.addValue(150)
	o2.addValue(200)

	doTicks(objs, 1.0)

	assert o1.getCounter() == 350
	assert o2.getCounter() == 350

	del o1
	del o2

	a = [getNextAddr(), getNextAddr()]
	o1 = TestObj(a[0], [a[1]], compactionTest=1, dumpFile = 'dump1.bin')
	o2 = TestObj(a[1], [a[0]], compactionTest=1, dumpFile = 'dump2.bin')
	objs = [o1, o2]
	doTicks(objs, 3.5)

	assert o1._getLeader() in a
	assert o1._getLeader() == o2._getLeader()

	assert o1.getCounter() == 350
	assert o2.getCounter() == 350

	removeFiles(['dump1.bin', 'dump2.bin'])


def runTests():
	syncTwoObjects()
	syncThreeObjectsLeaderFail()
	manyActionsLogCompaction()
	checkCallbacksSimple()
	checkDumpToFile()
	print '[SUCCESS]'

if __name__ == '__main__':
	runTests()