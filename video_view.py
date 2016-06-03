import gobject, pygst
pygst.require('0.10')
import gst
from PyQt4 import QtCore, QtGui
import sys, random, cv, gtk, time

class Video(QtGui.QMainWindow):
	def __init__(self):
		QtGui.QMainWindow.__init__(self)
		container = QtGui.QWidget()
		self.setCentralWidget(container)
		self.windowId = container.winId()
		
		self.windowId = container.winId()
		self.setGeometry(300,300, 800, 600)
		
		self.show()
		
		self.pipeline = gst.Pipeline("pipeline")
	
	def setupUSBCam(self):
		
		self.source = gst.element_factory_make("v4l2src", "source")
		self.source.set_property("device", "/dev/video0")
		self.pipeline.add(self.source)
		
		fvidscale_cap = gst.element_factory_make("capsfilter", "fvidscale_cap")
		fvidscale = gst.element_factory_make("videoscale", "fvidscale")
		caps = gst.caps_from_string('video/x-raw-rgb,width=800,height=600')
		fvidscale_cap.set_property('caps', caps)
		self.pipeline.add(fvidscale)
		self.pipeline.add(fvidscale_cap)
		
	def setupRTSPCam(self):
		
		self.source = gst.element_factory_make("rtspsrc", "source")
		self.source.set_property("location", "rtsp://localhost:9400/stream")
		self.source.connect('pad-added', self.on_new_stream)
		#add the rtpsource to the pipeline
		self.pipeline.add(self.source)
		
		self.decode = gst.element_factory_make("decodebin", "decode")
		self.decode.connect('new-decoded-pad', self.on_new_decoded)
		
		
		self.pipeline.add(self.decode)
		
		

	def on_new_stream(self, element, pad):
		
		decode = self.pipeline.get_by_name('decode').get_pad("sink")
		pad.link(decode.get_pad('sink'))
		
		
	def on_new_decoded(self, dbin, pad):
		decode = pad.get_parent()
		pipeline = decode.get_parent()
		convert = pipeline.get_by_name('conv1')
		decode.link(convert)
		pipeline.set_state(gst.STATE_PLAYING)
		print "linked!"
		
	def setupStream(self):		
		conv1 = gst.element_factory_make('ffmpegcolorspace', 'conv1')
		self.pipeline.add(conv1)
		conv2 = gst.element_factory_make('ffmpegcolorspace', 'conv2')
		self.pipeline.add(conv2)
		tee = gst.element_factory_make("tee", "tee")
		self.pipeline.add(tee)
		
		screen_queue = gst.element_factory_make("queue", "screen_queue")
		self.pipeline.add(screen_queue)

#		/* Creates separate thread for the stream from which the image
#		 * is captured */
		
		image_queue = gst.element_factory_make("queue", "image_queue")
		self.pipeline.add(image_queue)
		
		screen_sink = gst.element_factory_make ("xvimagesink", "screen_sink")
		
		fake_jpeg = gst.element_factory_make( "jpegenc", "jpegenc" )
		
		
		image_sink = gst.element_factory_make('fakesink', 'image_sink')
		image_sink.set_property("signal-handoffs", True)
		image_sink.connect('handoff', self.fsink_handoff_handle)
		
		
		screen_sink.set_property('sync', 'false')
		image_sink.set_property('sync', 'false')
		self.pipeline.add(screen_sink)
		self.pipeline.add(image_sink)
		self.pipeline.add(fake_jpeg)
		
		caps_yuv = gst.caps_from_string("video/x-raw-rgb")
		self.caps_rgb = gst.caps_from_string("video/x-raw-rgb")
		
		#~ self.decode.link(conv1, caps_rgb)
		conv1.link(tee)
		tee.link(screen_queue)
		screen_queue.link(conv2)
		conv2.link(screen_sink)

		tee.link(image_queue)
		
		image_queue.link(fake_jpeg)
		fake_jpeg.link(image_sink)

		
		bus = self.pipeline.get_bus()
		bus.add_signal_watch()
		bus.enable_sync_message_emission()
		bus.connect("sync-message::element", self.on_sync_message)
		bus.connect("message", self.on_message)
		
		self.start_preview()
			
	def fsink_handoff_handle(self, element, buff, pad):
		''''''
		self.buffer = buff.copy_on_write()

	def on_message(self, bus, message):
		
		t = message.type
		if t == gst.MESSAGE_EOS:
			self.pipeline.set_state(gst.STATE_NULL)
			print "end of message"
		elif t == gst.MESSAGE_ERROR:
			err, debug = message.parse_error()
			print "Error: %s" % err, debug
			self.pipeline.set_state(gst.STATE_NULL)

	def on_sync_message(self, bus, message):
		if message.structure is None:
			return
		message_name = message.structure.get_name()
		if message_name == "prepare-xwindow-id":
			win_id = self.windowId
			assert win_id
			imagesink = message.src
			imagesink.set_xwindow_id(win_id)

	def start_preview(self):
		self.pipeline.set_state(gst.STATE_PLAYING)
		print "should be playing"
		
	def stop_preview(self):
		"""
		Stop the preview from the camera
		"""
		if self.pipeline:
			self.pipe.set_state(gst.STATE_NULL)
			print "should be stopped"	
	
	def capture_frame(self):
		success, state, pending = self.pipeline.get_state(1)
		lcl = time.localtime(time.time())
		fmta = '%A' #week day
		fmtd = '%d' #day in numbers
		fmtb = '%b' #month with letters
		fmty = '%Y' #year
		fmth = '%H.%M.%S'
		
		self.stria = time.strftime(fmta,lcl)
		self.strid = time.strftime(fmtd,lcl)
		self.strib = time.strftime(fmtb,lcl)
		self.striy = time.strftime(fmty,lcl)
		self.strih = time.strftime(fmth,lcl)
		
		pixmap = QtGui.QPixmap()
		
		if not pending:
			if state == gst.STATE_PLAYING:
				if len(self.buffer) > 0:
					print len(self.buffer)
					print self.width(), self.height()
					print pixmap.loadFromData(self.buffer)
					pixmap = pixmap.scaled(800,600)
					pixmap.save(self.strid + '-' +self.strib+ '-' + 
                            self.striy + '-' +self.strih + '.png')
				else:
					print "Image failed"
		return pixmap

if __name__ == "__main__":
    gobject.threads_init()
    app = QtGui.QApplication(sys.argv)
    video = Video()
    
    video.setupRTSPCam()
    video.setupStream()
    #~ video.capture_frame()
    #~ video.start_preview()
    sys.exit(app.exec_())
