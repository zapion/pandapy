#PandaPy v1.1.2 by F.P.S. Luus, http://pandapy.googlecode.com/

#~ This program is free software: you can redistribute it and/or modify
    #~ it under the terms of the GNU General Public License as published by
    #~ the Free Software Foundation, either version 3 of the License, or
    #~ (at your option) any later version.

    #~ This program is distributed in the hope that it will be useful,
    #~ but WITHOUT ANY WARRANTY; without even the implied warranty of
    #~ MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    #~ GNU General Public License for more details.

    #~ You should have received a copy of the GNU General Public License
    #~ along with this program.  If not, see <http://www.gnu.org/licenses/>.

#1) Install Python for S60 v1.4.5 and Python Script Shell for your specific phone OS type, http://sourceforge.net/project/showfiles.php?group_id=154155&package_id=171153&release_id=644640
#2) Create dir C:\Python\ on your phone
#3) Run PandaPy_v1_1_2.py from Script Shell

#Fix 2: Speech functionality: If a capture happens, the move is not spoken.
#Fix 3: Corrected adjourned observed game status message
#Feature 4: Observation game blitz filter added
#Feature 5: Added Scrolling mode that allows for scrolling backward and forward through the game
#Feature 6: Added tell thank you for playing. message at end of played game
#Feature 7: Added landscape view
#Fix 8: Rewrote mark dead groups graphics to be more stack-friendly
#Fix 9: Undo scoring functionality corrected
#Fix 10: Corrected various small notification messages

#Fix 1 for v1.1.0: Unwanted disconnection after long observation fixed
#Fix 2 for v1.1.0: Synchronize remaining playing time if the connection has a high latency

import sys, appuifw, e32, socket, thread, graphics
import key_codes, time, copy, sysinfo, e32dbm, audio

class SocketProxy(object):
    def __init__(self, _address, _apid, _app):
        self.app = _app

        self.address = _address    #('igs.joyjoy.net', 6969)
        self.apid = _apid            #apid = socket.select_access_point() in main thread, because GUI function
        self.recv_buf = ''
        self.send_buf = ''
        self.comms_buf = ''

        self.lock = thread.allocate_lock()

        self.sent_bytes = 0
        self.recv_bytes = 0

        self.sent = 0
        self.stop_var = 0

        self.lasttransmit = time.clock()
        self.connected = 0
        thread.start_new_thread(self.connection_thread, ())

    def send(self, _tosend):
        self.sent = 0

        while not self.lock.acquire(0):
            pass
            e32.ao_yield()
        self.send_buf += _tosend
        self.lock.release()

        while not self.sent:
            pass
            e32.ao_yield()

    def recv(self):
        if (len(self.recv_buf)>0):
            while not self.lock.acquire(0):
                pass
                e32.ao_yield()
            temp = self.recv_buf
            #debug line
            self.comms_buf += self.recv_buf
            self.recv_buf = ''
            self.lock.release()
            return temp
        return ''

    def stop(self):
        self.stop_var = 1

    def connection_thread(self):
        try:
            socket.set_default_access_point(socket.access_point(self.apid))
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            while sock.connect(self.address):
                pass
                e32.ao_yield()

            sock.setblocking(0)
            self.connected = 1
        except:
            self.app.notification = 'Could not connect'
            return
        #print 'connected'
        while  not self.stop_var:
            try:
                #print 'ct',

                if len(self.send_buf)> 0:
                    while not self.lock.acquire(0):
                        pass
                        e32.ao_yield()
                    if sock.send(self.send_buf)< len(self.send_buf):
                        print 'socket problem'
                    #print 'Sent:', self.send_buf

                    self.sent_bytes += len(self.send_buf)
                    self.send_buf = ''
                    self.lasttransmit = time.clock()
                    self.lock.release()
                    self.sent = 1

                elif (time.clock() - self.lasttransmit > 30):
                    transmitupdate = '\r\n'
                    while not self.lock.acquire(0):
                        pass
                        e32.ao_yield()
                    if sock.send(transmitupdate)< len(transmitupdate):
                        print 'socket problem'
                    #print 'Sent:', self.send_buf

                    self.sent_bytes += len(transmitupdate)
                    self.lasttransmit = time.clock()
                    self.lock.release()

                while not self.lock.acquire(0):
                    pass
                    e32.ao_yield()
                temp = len(self.recv_buf)
                try:
                    self.recv_buf += sock.recv(1)
                except:
                    pass
                if temp< len(self.recv_buf):
                    self.recv_bytes += 1
                    #print self.recv_buf

                self.lock.release()
                e32.ao_yield()
            except:
                try:
                    sock.close()
                except:
                    pass
                self.connected = 0
                self.app.notification = 'Disconnected'
                return
            #~ e32.ao_yield()
        sock.close()
        self.connected = 0

class PersistentStorage:
    def __init__(self,filename):
        try:
            # Try to open an existing file
            self.data = e32dbm.open(filename,"w")
        except:
            # Failed: Assume the file needs to be created
            self.data = e32dbm.open(filename,"n")

    def SetValue(self,key,value):
        if str(value) == value:
            # if value is a string, it needs special treatment
            self.data[key] = "u\"%s\"" % value
        else:
            # otherwise simply convert it to a string
            self.data[key] = str(value)

    def GetValue(self,key):
        try:
            return eval(self.data[key])
        except:
            # Assume item doesn't exist (yet), so return None
            return None

    def Close(self):
        self.data.close()

class PlayerInfo(object):
    def __init__(self):
        self.name = ''
        self.strength = ''
        self.game_number = -1
        self.observenumber = -1
        self.idle = ''
        self.quiet_on = 0
        self.shout_off = 0
        self.open_off = 0
        self.looking_on  = 0

    def display(self):
        try:
            print self.name,self.strength ,self.game_number,self.observenumber,self.idle,self.quiet_on,self.shout_off ,self.open_off ,self.looking_on
        except:
            raise

class GameInfo(object):
    def __init__(self):
        self.white_name = ''
        self.black_name = ''
        self.game_number = 0
        self.white_strength = ''
        self.black_strength = ''
        self.moves_played = 0
        self.size = 0
        self.handi = 0
        self.komi = 0
        self.BY = 0
        self.FR = ''
        self.last_column = ''

    def display(self):
        print self.white_name,self.black_name,self.game_number,self.white_strength,self.black_strength ,self.moves_played,self.size,self.handi,self.komi,self.BY,self.FR ,self.last_column

    def oneline(self):
        temp_ws = self.white_strength.rstrip('*')
        temp_bs = self.black_strength.rstrip('*')
        return str(self.moves_played) + ' '+ self.white_name[0:3]+' '+temp_ws+'<'+'>'+temp_bs+' '+self.black_name[0:3]

class BoardView(object):
    def __init__(self, _width, _length):
        self.width = _width
        self.length = _length
        self.zoom = 1.0
        self.board = [[' ' for i in range(19)] for j in range(19)]
        self.cursor = (9,9)
        self.view_center = (9,9)

        self.image_width = (int)(self.width/(19.0*2.0))*2*19+3
        self.da = (int)(self.width*self.zoom/(19.0*2.0))
        self.da2 = 2*self.da
        self.da19 = 19*self.da2
        self.da20 = 20*self.da2
        self.x0, self.y0 = (1,1)
        self.xbegin = self.x0+self.da
        self.xend = self.x0+self.da19+1-self.da
        self.ytemp = self.y0-self.da
        self.xtemp = self.x0-self.da
        self.ybegin = self.y0+self.da
        self.yend = self.y0+self.da19+1-self.da
        self.clean_board = 0
        self.board_image = 0
        self.curr_image = 0

    def update(self, _board, _zoom, _cursor, _orient):
        #_orient if 0 then portrait if 1 then landscape
        if (self.board == _board) and (self.zoom == _zoom) and (self.cursor == _cursor) and self.curr_image:
            return self.curr_image

        if (self.zoom == _zoom) and (self.cursor != _cursor):
            temp_u = int(19.0/self.zoom/2.0)-1

            if abs(_cursor[0] - self.view_center[0]) > temp_u:
                if _cursor[0]<self.view_center[0]:
                    self.view_center = (_cursor[0]+temp_u, self.view_center[1])
                if _cursor[0]>self.view_center[0]:
                    self.view_center = (_cursor[0]-temp_u, self.view_center[1])
                if self.view_center[0]<0:
                    self.view_center = (0, self.view_center[1])
                if self.view_center[0]>18:
                    self.view_center = (18, self.view_center[1])
            if abs(_cursor[1] - self.view_center[1]) > temp_u:
                if _cursor[1]<self.view_center[1]:
                    self.view_center = (self.view_center[0], _cursor[1]+temp_u)
                if _cursor[1]>self.view_center[1]:
                    self.view_center = (self.view_center[0], _cursor[1]-temp_u)
                if self.view_center[1]<0:
                    self.view_center = (self.view_center[0], 0)
                if self.view_center[1]>18:
                    self.view_center = (self.view_center[0], 18)

        elif (_zoom == 100.0) and (self.cursor != _cursor):
            temp_u = int(19.0/self.zoom/2.0)-1
            if _orient:
                temp_u += 1
            if abs(_cursor[0] - self.view_center[0]) > temp_u:
                if _cursor[0]<self.view_center[0]:
                    self.view_center = (_cursor[0]+temp_u, self.view_center[1])
                if _cursor[0]>self.view_center[0]:
                    self.view_center = (_cursor[0]-temp_u, self.view_center[1])
                if self.view_center[0]<0:
                    self.view_center = (0, self.view_center[1])
                if self.view_center[0]>18:
                    self.view_center = (18, self.view_center[1])
            temp_u = int(19.0/self.zoom/2.0)
            if _orient:
                temp_u -= 1
            if abs(_cursor[1] - self.view_center[1]) > temp_u:
                if _cursor[1]<self.view_center[1]:
                    self.view_center = (self.view_center[0], _cursor[1]+temp_u)
                if _cursor[1]>self.view_center[1]:
                    self.view_center = (self.view_center[0], _cursor[1]-temp_u)
                if self.view_center[1]<0:
                    self.view_center = (self.view_center[0], 0)
                if self.view_center[1]>18:
                    self.view_center = (self.view_center[0], 18)

        if (self.board == _board) and ((self.zoom == _zoom) or (_zoom == 100.0)) and (self.cursor != _cursor) and self.board_image:
            x, y = _cursor
            self.cursor = _cursor
            if not(x==-1 or y==-1):
                temp = graphics.Image.new((self.da19+3, self.da19+3))
                temp.clear(0)
                temp.blit(self.board_image, target=(0,0))
                temp.ellipse((self.x0+self.da2*x+self.da-2, self.y0+self.da2*y+self.da-2, self.x0+self.da2*x+self.da+3, self.y0+self.da2*y+self.da+3), fill=(4, 105, 172), outline=(4, 105, 172))

                temp_v = int(19.0/self.zoom)
                temp_u = int(19.0/self.zoom/2.0)

                temp_x = self.view_center[0] - temp_u
                if _zoom == 100.0 and _orient:
                    temp_x -= 2
                if temp_x>18-temp_v:
                    temp_x = 18-temp_v
                if _zoom == 100.0 and _orient and temp_x>14-temp_v:
                    temp_x = 14-temp_v
                if temp_x<0:
                    temp_x = 0

                temp_y = self.view_center[1] - temp_u
                if _zoom == 100.0 and not _orient:
                    temp_y -= 2
                if temp_y>18-temp_v:
                    temp_y = 18-temp_v
                if _zoom == 100.0 and not _orient and temp_y>14-temp_v:
                    temp_y = 14-temp_v
                if temp_y<0:
                    temp_y = 0


                curr_image = 0
                if _zoom == 100.0:
                    if not _orient:
                        curr_image = graphics.Image.new((self.width, self.length))
                        curr_image.clear(0)
                        curr_image.blit(temp, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.width, self.y0+self.da2*temp_y-1+self.length)))
                    else:
                        curr_image = graphics.Image.new((self.length, self.width))
                        curr_image.clear(0)
                        curr_image.blit(temp, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.length, self.y0+self.da2*temp_y-1+self.width)))
                else:
                    curr_image = graphics.Image.new((self.width, self.width))
                    curr_image.clear(0)
                    curr_image.blit(temp, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.width, self.y0+self.da2*temp_y-1+self.width)))
                self.curr_image = curr_image
                return curr_image

        if (self.zoom != _zoom and _zoom != 100.0) or not self.clean_board:
            self.view_center = _cursor

            if not (_zoom == 100.0):
                self.zoom = _zoom
            self.image_width = (int)(self.width/(19.0*2.0))*2*19+3

            self.da = (int)(self.width*self.zoom/(19.0*2.0))
            self.da2 = 2*self.da
            self.da19 = 19*self.da2
            self.da20 = 20*self.da2
            self.x0, self.y0 = (1,1)
            self.xbegin = self.x0+self.da
            self.xend = self.x0+self.da19+1-self.da
            self.ytemp = self.y0-self.da
            self.xtemp = self.x0-self.da
            self.ybegin = self.y0+self.da
            self.yend = self.y0+self.da19+1-self.da

            clean_board = graphics.Image.new((self.da19+3, self.da19+3))
            clean_board.clear(0)
            clean_board.rectangle((self.x0-1, self.y0-1, self.x0+self.da19+2, self.y0+self.da19+2), fill=(234, 192, 93))

            for i in range(1, 20):
                temp = self.da2*i
                clean_board.line(((self.xbegin, self.ytemp+temp), (self.xend, self.ytemp+temp)), 0x0)
                clean_board.line(((self.xtemp+temp, self.ybegin), (self.xtemp+temp, self.yend)), 0x0)

            for x,y in ((3,3),(3,9),(3,15),(9,3),(9,9),(9,15),(15,3),(15,9),(15,15)):
                clean_board.line(((self.x0+self.da2*x+self.da-1, self.y0+self.da2*y+self.da-1), (self.x0+self.da2*x+self.da+2, self.y0+self.da2*y+self.da-1)), 0x0)
                clean_board.line(((self.x0+self.da2*x+self.da-1, self.y0+self.da2*y+self.da+1), (self.x0+self.da2*x+self.da+2, self.y0+self.da2*y+self.da+1)), 0x0)
            self.clean_board = clean_board

        curr_image = 0
        board_image = 0
        board_image = graphics.Image.new((self.da19+3, self.da19+3))
        board_image.clear(0)
        board_image.blit(self.clean_board, target=(0,0))

        white_stone = graphics.Image.new((101, 101))
        white_stone.ellipse((6, 6, 94, 94), fill=0xffffff, outline=0, width=6)
        white_stone=white_stone.resize((self.da2+2,self.da2+2), keepaspect=1)

        stone_mask = graphics.Image.new((101, 101), mode='L')
        stone_mask.clear(0)
        stone_mask.ellipse((6, 6, 94, 94), fill=0xffffff, outline=0xffffff, width=3)
        stone_mask=stone_mask.resize((self.da2+2,self.da2+2), keepaspect=1)

        black_stone = graphics.Image.new((101, 101))
        black_stone.ellipse((6, 6, 94, 94), fill=0, outline=(10, 10, 10),width=6)
        black_stone=black_stone.resize((self.da2+2,self.da2+2), keepaspect=1)

        self.board = _board
        for c,x,y in self.board:
            if c == 'W':
                board_image.blit(white_stone, target=(self.x0+self.da2*x-1,self.y0+self.da2*y-1), mask = stone_mask)
            elif c == 'B':
                board_image.blit(black_stone, target=(self.x0+self.da2*x-1,self.y0+self.da2*y-1), mask = stone_mask)
            elif c == 'w':
                board_image.ellipse((self.x0+self.da2*x+self.da-2, self.y0+self.da2*y+self.da-2, self.x0+self.da2*x+self.da+3, self.y0+self.da2*y+self.da+3), fill=0xffffff, outline=0xffffff)
            elif c == 'b':
                board_image.ellipse((self.x0+self.da2*x+self.da-2, self.y0+self.da2*y+self.da-2, self.x0+self.da2*x+self.da+3, self.y0+self.da2*y+self.da+3), fill=0x0, outline=0)

        if len(self.board):
            c, x, y = self.board[-1]
            if not c == 'w' and not c == 'b':
                board_image.ellipse((self.x0+self.da2*x+self.da-2, self.y0+self.da2*y+self.da-2, self.x0+self.da2*x+self.da+3, self.y0+self.da2*y+self.da+3), fill=(200, 0, 0), outline=(200, 0, 0))

        self.cursor = _cursor
        x, y = _cursor
        if not(x==-1 or y==-1):
            temp = graphics.Image.new((self.da19+3, self.da19+3))
            temp.clear(0)
            temp.blit(board_image, target=(0,0))
            temp.ellipse((self.x0+self.da2*x+self.da-2, self.y0+self.da2*y+self.da-2, self.x0+self.da2*x+self.da+3, self.y0+self.da2*y+self.da+3), fill=(4, 105, 172), outline=(4, 105, 172))

            temp_v = int(19.0/self.zoom)
            temp_u = int(19.0/self.zoom/2.0)

            temp_x = self.view_center[0] - temp_u
            if _zoom == 100.0 and _orient:
                temp_x -= 2
            if temp_x>18-temp_v:
                temp_x = 18-temp_v
            if _zoom == 100.0 and _orient and temp_x>14-temp_v:
                temp_x = 14-temp_v
            if temp_x<0:
                temp_x = 0

            temp_y = self.view_center[1] - temp_u
            if _zoom == 100.0 and not _orient:
                temp_y -= 2
            if temp_y>18-temp_v:
                temp_y = 18-temp_v
            if _zoom == 100.0 and not _orient and temp_y>14-temp_v:
                temp_y = 14-temp_v
            if temp_y<0:
                temp_y = 0

            curr_image = 0
            if _zoom == 100.0:
                if not _orient:
                    curr_image = graphics.Image.new((self.width, self.length))
                    curr_image.clear(0)
                    curr_image.blit(temp, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.width, self.y0+self.da2*temp_y-1+self.length)))
                else:
                    curr_image = graphics.Image.new((self.length, self.width))
                    curr_image.clear(0)
                    curr_image.blit(temp, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.length, self.y0+self.da2*temp_y-1+self.width)))
            else:
                curr_image = graphics.Image.new((self.width, self.width))
                curr_image.clear(0)
                curr_image.blit(temp, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.width, self.y0+self.da2*temp_y-1+self.width)))
            return curr_image

        temp_v = int(19.0/self.zoom)
        temp_u = int(19.0/self.zoom/2.0)
        temp_x = self.view_center[0] - temp_u

        if temp_x>18-temp_v:
            temp_x = 18-temp_v
        if temp_x<0:
            temp_x = 0
        temp_y = self.view_center[1] - temp_u
        if _zoom == 100.0:
            temp_y -= 2
        if temp_y>18-temp_v:
            temp_y = 18-temp_v
        if _zoom == 100.0 and temp_y>14-temp_v:
            temp_y = 14-temp_v
        if temp_y<0:
            temp_y = 0
        curr_image = 0
        if _zoom == 100:
            if not _orient:
                curr_image = graphics.Image.new((self.width, self.length))
                curr_image.clear(0)
                curr_image.blit(board_image, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.width, self.y0+self.da2*temp_y-1+self.length)))
            else:
                curr_image = graphics.Image.new((self.length, self.width))
                curr_image.clear(0)
                curr_image.blit(board_image, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.length, self.y0+self.da2*temp_y-1+self.width)))
        else:
            curr_image = graphics.Image.new((self.width, self.width))
            curr_image.clear(0)
            curr_image.blit(board_image, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.width, self.y0+self.da2*temp_y-1+self.width)))

        self.curr_image = curr_image
        self.board_image = board_image
        return curr_image

    def oldupdate(self, _board, _zoom, _prevmove, _lastmove, _cursor, _orient):
        #_prevmove = x,y or 0, if 0 then not simple next move, redraw all stones, otherwise draw _prevmove and _lastmove
        #_lastmove = x,y coordinates of last move, contained in board
        #_orient if 0 then portrait if 1 then landscape
        if (self.board == _board) and (self.zoom == _zoom) and (self.cursor == _cursor) and self.curr_image:
            return self.curr_image

        if (self.zoom == _zoom) and (self.cursor != _cursor):
            temp_u = int(19.0/self.zoom/2.0)-1

            if abs(_cursor[0] - self.view_center[0]) > temp_u:
                if _cursor[0]<self.view_center[0]:
                    self.view_center = (_cursor[0]+temp_u, self.view_center[1])
                if _cursor[0]>self.view_center[0]:
                    self.view_center = (_cursor[0]-temp_u, self.view_center[1])
                if self.view_center[0]<0:
                    self.view_center = (0, self.view_center[1])
                if self.view_center[0]>18:
                    self.view_center = (18, self.view_center[1])
            if abs(_cursor[1] - self.view_center[1]) > temp_u:
                if _cursor[1]<self.view_center[1]:
                    self.view_center = (self.view_center[0], _cursor[1]+temp_u)
                if _cursor[1]>self.view_center[1]:
                    self.view_center = (self.view_center[0], _cursor[1]-temp_u)
                if self.view_center[1]<0:
                    self.view_center = (self.view_center[0], 0)
                if self.view_center[1]>18:
                    self.view_center = (self.view_center[0], 18)

        elif (_zoom == 100.0) and (self.cursor != _cursor):
            temp_u = int(19.0/self.zoom/2.0)-1
            if _orient:
                temp_u += 1
            if abs(_cursor[0] - self.view_center[0]) > temp_u:
                if _cursor[0]<self.view_center[0]:
                    self.view_center = (_cursor[0]+temp_u, self.view_center[1])
                if _cursor[0]>self.view_center[0]:
                    self.view_center = (_cursor[0]-temp_u, self.view_center[1])
                if self.view_center[0]<0:
                    self.view_center = (0, self.view_center[1])
                if self.view_center[0]>18:
                    self.view_center = (18, self.view_center[1])
            temp_u = int(19.0/self.zoom/2.0)
            if _orient:
                temp_u -= 1
            if abs(_cursor[1] - self.view_center[1]) > temp_u:
                if _cursor[1]<self.view_center[1]:
                    self.view_center = (self.view_center[0], _cursor[1]+temp_u)
                if _cursor[1]>self.view_center[1]:
                    self.view_center = (self.view_center[0], _cursor[1]-temp_u)
                if self.view_center[1]<0:
                    self.view_center = (self.view_center[0], 0)
                if self.view_center[1]>18:
                    self.view_center = (self.view_center[0], 18)

        if (self.board == _board) and ((self.zoom == _zoom) or (_zoom == 100.0)) and (self.cursor != _cursor) and self.board_image:
            x, y = _cursor
            self.cursor = _cursor
            if not(x==-1 or y==-1):
                temp = graphics.Image.new((self.da19+3, self.da19+3))
                temp.clear(0)
                temp.blit(self.board_image, target=(0,0))
                temp.ellipse((self.x0+self.da2*x+self.da-2, self.y0+self.da2*y+self.da-2, self.x0+self.da2*x+self.da+3, self.y0+self.da2*y+self.da+3), fill=(4, 105, 172), outline=(4, 105, 172))

                temp_v = int(19.0/self.zoom)
                temp_u = int(19.0/self.zoom/2.0)

                temp_x = self.view_center[0] - temp_u
                if _zoom == 100.0 and _orient:
                    temp_x -= 2
                if temp_x>18-temp_v:
                    temp_x = 18-temp_v
                if _zoom == 100.0 and _orient and temp_x>14-temp_v:
                    temp_x = 14-temp_v
                if temp_x<0:
                    temp_x = 0

                temp_y = self.view_center[1] - temp_u
                if _zoom == 100.0 and not _orient:
                    temp_y -= 2
                if temp_y>18-temp_v:
                    temp_y = 18-temp_v
                if _zoom == 100.0 and not _orient and temp_y>14-temp_v:
                    temp_y = 14-temp_v
                if temp_y<0:
                    temp_y = 0


                curr_image = 0
                if _zoom == 100.0:
                    if not _orient:
                        curr_image = graphics.Image.new((self.width, self.length))
                        curr_image.clear(0)
                        curr_image.blit(temp, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.width, self.y0+self.da2*temp_y-1+self.length)))
                    else:
                        curr_image = graphics.Image.new((self.length, self.width))
                        curr_image.clear(0)
                        curr_image.blit(temp, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.length, self.y0+self.da2*temp_y-1+self.width)))
                else:
                    curr_image = graphics.Image.new((self.width, self.width))
                    curr_image.clear(0)
                    curr_image.blit(temp, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.width, self.y0+self.da2*temp_y-1+self.width)))
                self.curr_image = curr_image
                return curr_image

        if (self.zoom != _zoom and _zoom != 100.0) or not self.clean_board:
            self.view_center = _cursor

            if not (_zoom == 100.0):
                self.zoom = _zoom
            self.image_width = (int)(self.width/(19.0*2.0))*2*19+3

            self.da = (int)(self.width*self.zoom/(19.0*2.0))
            self.da2 = 2*self.da
            self.da19 = 19*self.da2
            self.da20 = 20*self.da2
            self.x0, self.y0 = (1,1)
            self.xbegin = self.x0+self.da
            self.xend = self.x0+self.da19+1-self.da
            self.ytemp = self.y0-self.da
            self.xtemp = self.x0-self.da
            self.ybegin = self.y0+self.da
            self.yend = self.y0+self.da19+1-self.da

            clean_board = graphics.Image.new((self.da19+3, self.da19+3))
            clean_board.clear(0)
            clean_board.rectangle((self.x0-1, self.y0-1, self.x0+self.da19+2, self.y0+self.da19+2), fill=(234, 192, 93))

            for i in range(1, 20):
                temp = self.da2*i
                clean_board.line(((self.xbegin, self.ytemp+temp), (self.xend, self.ytemp+temp)), 0x0)
                clean_board.line(((self.xtemp+temp, self.ybegin), (self.xtemp+temp, self.yend)), 0x0)

            for x,y in ((3,3),(3,9),(3,15),(9,3),(9,9),(9,15),(15,3),(15,9),(15,15)):
                clean_board.line(((self.x0+self.da2*x+self.da-1, self.y0+self.da2*y+self.da-1), (self.x0+self.da2*x+self.da+2, self.y0+self.da2*y+self.da-1)), 0x0)
                clean_board.line(((self.x0+self.da2*x+self.da-1, self.y0+self.da2*y+self.da+1), (self.x0+self.da2*x+self.da+2, self.y0+self.da2*y+self.da+1)), 0x0)
            self.clean_board = clean_board

        curr_image = 0
        board_image = 0
        board_image = graphics.Image.new((self.da19+3, self.da19+3))
        board_image.clear(0)
        board_image.blit(self.clean_board, target=(0,0))

        white_stone = graphics.Image.new((101, 101))
        white_stone.ellipse((6, 6, 94, 94), fill=0xffffff, outline=0, width=6)
        white_stone=white_stone.resize((self.da2+2,self.da2+2), keepaspect=1)

        stone_mask = graphics.Image.new((101, 101), mode='L')
        stone_mask.clear(0)
        stone_mask.ellipse((6, 6, 94, 94), fill=0xffffff, outline=0xffffff, width=3)
        stone_mask=stone_mask.resize((self.da2+2,self.da2+2), keepaspect=1)

        black_stone = graphics.Image.new((101, 101))
        black_stone.ellipse((6, 6, 94, 94), fill=0, outline=(10, 10, 10),width=6)
        black_stone=black_stone.resize((self.da2+2,self.da2+2), keepaspect=1)

        self.board = _board
        for x in range(0, 19):
            for y in range(0, 19):
                if self.board[x][y] == 'W':
                    board_image.blit(white_stone, target=(self.x0+self.da2*x-1,self.y0+self.da2*y-1), mask = stone_mask)
                    #board_image.ellipse((self.x0+self.da2*x, self.y0+self.da2*y, self.x0+self.da2*x+self.da2+1, self.y0+self.da2*y+self.da2+1), fill=0xffffff, outline=(103,77,14))
                elif self.board[x][y] == 'B':
                    board_image.blit(black_stone, target=(self.x0+self.da2*x-1,self.y0+self.da2*y-1), mask = stone_mask)
                    #board_image.ellipse((self.x0+self.da2*x, self.y0+self.da2*y, self.x0+self.da2*x+self.da2+1, self.y0+self.da2*y+self.da2+1), fill=0x0, outline=(103,77,14))
                elif self.board[x][y] == 'w':
                    board_image.ellipse((self.x0+self.da2*x+self.da-2, self.y0+self.da2*y+self.da-2, self.x0+self.da2*x+self.da+3, self.y0+self.da2*y+self.da+3), fill=0xffffff, outline=0xffffff)
                elif self.board[x][y] == 'b':
                    board_image.ellipse((self.x0+self.da2*x+self.da-2, self.y0+self.da2*y+self.da-2, self.x0+self.da2*x+self.da+3, self.y0+self.da2*y+self.da+3), fill=0x0, outline=0)

        x, y = _lastmove
        if not(x==-1 or y==-1):
            board_image.ellipse((self.x0+self.da2*x+self.da-2, self.y0+self.da2*y+self.da-2, self.x0+self.da2*x+self.da+3, self.y0+self.da2*y+self.da+3), fill=(200, 0, 0), outline=(200, 0, 0))

        self.cursor = _cursor
        x, y = _cursor
        if not(x==-1 or y==-1):
            temp = graphics.Image.new((self.da19+3, self.da19+3))
            temp.clear(0)
            temp.blit(board_image, target=(0,0))
            temp.ellipse((self.x0+self.da2*x+self.da-2, self.y0+self.da2*y+self.da-2, self.x0+self.da2*x+self.da+3, self.y0+self.da2*y+self.da+3), fill=(4, 105, 172), outline=(4, 105, 172))

            temp_v = int(19.0/self.zoom)
            temp_u = int(19.0/self.zoom/2.0)

            temp_x = self.view_center[0] - temp_u
            if _zoom == 100.0 and _orient:
                temp_x -= 2
            if temp_x>18-temp_v:
                temp_x = 18-temp_v
            if _zoom == 100.0 and _orient and temp_x>14-temp_v:
                temp_x = 14-temp_v
            if temp_x<0:
                temp_x = 0

            temp_y = self.view_center[1] - temp_u
            if _zoom == 100.0 and not _orient:
                temp_y -= 2
            if temp_y>18-temp_v:
                temp_y = 18-temp_v
            if _zoom == 100.0 and not _orient and temp_y>14-temp_v:
                temp_y = 14-temp_v
            if temp_y<0:
                temp_y = 0

            curr_image = 0
            if _zoom == 100.0:
                if not _orient:
                    curr_image = graphics.Image.new((self.width, self.length))
                    curr_image.clear(0)
                    curr_image.blit(temp, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.width, self.y0+self.da2*temp_y-1+self.length)))
                else:
                    curr_image = graphics.Image.new((self.length, self.width))
                    curr_image.clear(0)
                    curr_image.blit(temp, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.length, self.y0+self.da2*temp_y-1+self.width)))
            else:
                curr_image = graphics.Image.new((self.width, self.width))
                curr_image.clear(0)
                curr_image.blit(temp, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.width, self.y0+self.da2*temp_y-1+self.width)))
            return curr_image

        temp_v = int(19.0/self.zoom)
        temp_u = int(19.0/self.zoom/2.0)
        temp_x = self.view_center[0] - temp_u

        if temp_x>18-temp_v:
            temp_x = 18-temp_v
        if temp_x<0:
            temp_x = 0
        temp_y = self.view_center[1] - temp_u
        if _zoom == 100.0:
            temp_y -= 2
        if temp_y>18-temp_v:
            temp_y = 18-temp_v
        if _zoom == 100.0 and temp_y>14-temp_v:
            temp_y = 14-temp_v
        if temp_y<0:
            temp_y = 0
        curr_image = 0
        if _zoom == 100:
            if not _orient:
                curr_image = graphics.Image.new((self.width, self.length))
                curr_image.clear(0)
                curr_image.blit(board_image, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.width, self.y0+self.da2*temp_y-1+self.length)))
            else:
                curr_image = graphics.Image.new((self.length, self.width))
                curr_image.clear(0)
                curr_image.blit(board_image, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.length, self.y0+self.da2*temp_y-1+self.width)))
        else:
            curr_image = graphics.Image.new((self.width, self.width))
            curr_image.clear(0)
            curr_image.blit(board_image, target=(0,0), source=((self.x0+self.da2*temp_x-1, self.y0+self.da2*temp_y-1), (self.x0+self.da2*temp_x-1+self.width, self.y0+self.da2*temp_y-1+self.width)))

        self.curr_image = curr_image
        self.board_image = board_image
        return curr_image

class GameDefImg(object):
    def __init__(self, playing, handi, komi):
        self.img =  graphics.Image.new((100, 13))
        self.img.clear(0)
        temp_str = 'Observing ['
        if playing:
            temp_str = 'Playing ['
        if handi>0:
            temp_str += 'H'+str(handi)
        if komi<0 or komi>0:
            temp_str += ' '+str(komi)
        temp_str +=']'
        self.img.text((0,10), unicode(temp_str), fill=(255,255,255), font=(None, 10, graphics.FONT_BOLD))

    def get(self):
        return self.img

class GameScrollImg(object):
    def __init__(self, moves, position, toolow):
        self.img =  graphics.Image.new((70, 13))
        self.img.clear(0)
        if not toolow:
            self.img.text((1,10), unicode('#'+str(position+1)), fill=(0,255,0), font=(None, 10, graphics.FONT_BOLD))
        else:
            self.img.text((1,10), unicode('#'+str(position+1)), fill=(255,0,0), font=(None, 10, graphics.FONT_BOLD))
        self.img.text((30,10), unicode('['+str(moves+1)+']'), fill=(255,255,255), font=(None, 10, graphics.FONT_BOLD))

    def get(self):
        return self.img

class NamePaneImg(object):
    def __init__(self, whiten, blackn, whites, blacks):
        temp_wmove = graphics.Image.new((241, 32))
        temp_bmove = graphics.Image.new((241, 32))
        temp_wmove.clear(0)
        temp_bmove.clear(0)
        temp_wmove.rectangle((0, 0, 240, 2), fill=(187, 226, 253))
        temp_wmove.rectangle((0, 2, 240, 3), fill=(170, 220, 253))
        temp_wmove.rectangle((0, 3, 240, 13), fill=(154, 205, 252))
        temp_wmove.rectangle((0, 13, 240, 14), fill=(135, 199, 252))
        temp_wmove.rectangle((0, 14, 240, 15), fill=(120, 199, 252))

        temp_wmove.rectangle((126, 0, 196, 15), fill=(187, 226, 253))
        #temp_wmove.rectangle((196, 0, 198, 15), fill=(135, 199, 252))
        #~ temp_wmove.rectangle((0, 16, 240, 24), fill=0)
        temp_wmove.rectangle((0, 16, 240, 31), fill=(1, 21, 35))

        temp_bmove.rectangle((0, 0, 240, 15), fill=(1, 21, 35))
        #~ temp_bmove.rectangle((0, 8, 240, 15), fill=0)
        temp_bmove.rectangle((0, 16, 240, 18), fill=(187, 226, 253))
        temp_bmove.rectangle((0, 18, 240, 19), fill=(170, 220, 253))
        temp_bmove.rectangle((0, 19, 240, 29), fill=(154, 213, 252))
        temp_bmove.rectangle((0, 29, 240, 30), fill=(135, 199, 252))
        temp_bmove.rectangle((0, 30, 240, 31), fill=(120, 199, 252))

        temp_bmove.rectangle((126, 16, 196, 31), fill=(187, 226, 253))
        #temp_bmove.rectangle((196, 16, 198, 31), fill=(135, 199, 252))

        temp_wmove.text((14, 11), unicode(whiten + ' ['+whites+']'), fill=(0, 0, 0), font=(None, 13))
        temp_bmove.text((14, 11), unicode(whiten + ' ['+whites+']'), fill=(255, 255, 255), font=(None, 13))

        temp_wmove.text((14, 27), unicode(blackn + ' ['+blacks+']'), fill=(255, 255, 255), font=(None, 13))
        temp_bmove.text((14, 27), unicode(blackn + ' ['+blacks+']'), fill=(0, 0, 0), font=(None, 13))

        self.img_wmove = temp_wmove
        self.img_bmove = temp_bmove

        white_stone = graphics.Image.new((101, 101))
        white_stone.ellipse((6, 6, 94, 94), fill=0xffffff, outline=0, width=6)
        white_stone=white_stone.resize((12,12), keepaspect=1)

        stone_mask = graphics.Image.new((101, 101), mode='L')
        stone_mask.clear(0)
        stone_mask.ellipse((6, 6, 94, 94), fill=0xffffff, outline=0xffffff, width=6)
        stone_mask=stone_mask.resize((12,12), keepaspect=1)

        black_stone = graphics.Image.new((101, 101))
        black_stone.ellipse((6, 6, 94, 94), fill=0, outline=0xffffff,width=6)
        black_stone=black_stone.resize((12,12), keepaspect=1)

        self.img_wmove.blit(white_stone, target=(1,1), mask = stone_mask)
        self.img_wmove.blit(black_stone, target=(188+10,2), mask = stone_mask)
        self.img_wmove.blit(black_stone, target=(192+10,1), mask = stone_mask)
        self.img_wmove.blit(black_stone, target=(196+10,0), mask = stone_mask)

        self.img_wmove.blit(black_stone, target=(1,17), mask = stone_mask)
        self.img_wmove.blit(white_stone, target=(188+10,18), mask = stone_mask)
        self.img_wmove.blit(white_stone, target=(192+10,17), mask = stone_mask)
        self.img_wmove.blit(white_stone, target=(196+10,16), mask = stone_mask)

        self.img_bmove.blit(white_stone, target=(1,1), mask = stone_mask)
        self.img_bmove.blit(black_stone, target=(188+10,2), mask = stone_mask)
        self.img_bmove.blit(black_stone, target=(192+10,1), mask = stone_mask)
        self.img_bmove.blit(black_stone, target=(196+10,0), mask = stone_mask)

        self.img_bmove.blit(black_stone, target=(1,17), mask = stone_mask)
        self.img_bmove.blit(white_stone, target=(188+10,18), mask = stone_mask)
        self.img_bmove.blit(white_stone, target=(192+10,17), mask = stone_mask)
        self.img_bmove.blit(white_stone, target=(196+10,16), mask = stone_mask)

    def get(self, wmove, whitec, blackc, white_time, black_time, white_byos, black_byos, timestamp, gameover):
        if wmove:
            temp = graphics.Image.new((241, 32))
            temp.clear(0)
            temp.blit(self.img_wmove)

            temp.text((220, 11), unicode(whitec), fill=(0, 0, 0), font=(None, 13))
            temp.text((220, 27), unicode(blackc), fill=(255,255, 255), font=(None, 13))

            temp_t = time.clock()-timestamp

            if not gameover:
                temp_t = (white_time-temp_t)/60.0
            else:
                temp_t = white_time/60.0
            wsecs = int((temp_t-int(temp_t))*60.0)
            if (wsecs<10):
                wsecs = wsecs/100.0
                wsecs = str(wsecs)[2:4]
            elif wsecs == 0:
                wsecs = '00'
            else:
                wsecs = str(wsecs)
            if wsecs == '0':
                wsecs = '00'
            if temp_t>0:
                temp.text((130, 11), unicode(str(int(temp_t)) + ':' + wsecs+' ('+ str(white_byos)+')'), fill=(0,0,0), font=(None, 13, graphics.FONT_BOLD))
            else:
                temp.text((130, 11), unicode('0:00 ('+ str(white_byos)+')'), fill=(0,0,0), font=(None, 13, graphics.FONT_BOLD))

            temp_t = black_time/60.0
            bsecs = int((temp_t-int(temp_t))*60.0)
            if (bsecs<10):
                bsecs = bsecs/100.0
                bsecs = str(bsecs)[2:4]
            elif bsecs == 0:
                bsecs = '00'
            else:
                bsecs = str(bsecs)
            if bsecs == '0':
                bsecs = '00'
            if temp_t>0:
                temp.text((130, 27), unicode(str(int(temp_t)) + ':' + bsecs+' ('+ str(black_byos)+')'), fill=(255,255,255), font=(None, 13, graphics.FONT_BOLD))
            else:
                temp.text((130, 27), unicode('0:00 ('+ str(black_byos)+')'), fill=(255,255,255), font=(None, 13, graphics.FONT_BOLD))


            return temp
        else:
            temp = graphics.Image.new((240, 32))
            temp.clear(0)
            temp.blit(self.img_bmove)

            temp.text((220, 11), unicode(whitec), fill=(255,255, 255), font=(None, 13))
            temp.text((220, 27), unicode(blackc), fill=(0, 0, 0), font=(None, 13))



            temp_t = white_time/60.0
            wsecs = int((temp_t-int(temp_t))*60.0)
            if (wsecs<10):
                wsecs = wsecs/100.0
                wsecs = str(wsecs)[2:4]
            elif wsecs == 0:
                wsecs = '00'
            else:
                wsecs = str(wsecs)
            if wsecs == '0':
                wsecs = '00'
            if temp_t>0:
                temp.text((130, 11), unicode(str(int(temp_t)) + ':' + wsecs+' ('+ str(white_byos)+')'), fill=(255,255,255), font=(None, 13, graphics.FONT_BOLD))
            else:
                temp.text((130, 11), unicode('0:00 ('+ str(white_byos)+')'), fill=(255,255,255), font=(None, 13, graphics.FONT_BOLD))

            temp_t = time.clock()-timestamp
            if not gameover:
                temp_t = (black_time-temp_t)/60.0
            else:
                temp_t = black_time/60.0
            bsecs = int((temp_t-int(temp_t))*60.0)
            if (bsecs<10):
                bsecs = bsecs/100.0
                bsecs = str(bsecs)[2:4]
            elif bsecs == 0:
                bsecs = '00'
            else:
                bsecs = str(bsecs)
            if bsecs == '0':
                bsecs = '00'
            if temp_t>0:
                temp.text((130, 27), unicode(str(int(temp_t)) + ':' + bsecs+' ('+ str(black_byos)+')'), fill=(0,0,0), font=(None, 13, graphics.FONT_BOLD))
            else:
                temp.text((130, 27), unicode('0:00 ('+ str(black_byos)+')'), fill=(0,0,0), font=(None, 13, graphics.FONT_BOLD))

            return temp

class NamePaneLandscapeImg(object):
    def __init__(self, whiten, blackn, whites, blacks):
        temp_wmove = graphics.Image.new((88, 128))
        temp_bmove = graphics.Image.new((88, 128))
        temp_wmove.clear(0)
        temp_bmove.clear(0)

        temp_wmove.rectangle((0, 0, 87, 2), fill=(187, 226, 253))
        temp_wmove.rectangle((0, 2, 87, 3), fill=(170, 220, 253))
        temp_wmove.rectangle((0, 3, 87, 45), fill=(154, 205, 252))
        temp_wmove.rectangle((0, 45, 87, 46), fill=(135, 199, 252))
        temp_wmove.rectangle((0, 46, 87, 47), fill=(120, 199, 252))
        temp_wmove.rectangle((0, 47, 87, 63), fill=(187, 226, 253))
        temp_wmove.rectangle((0, 64, 87, 127), fill=(1, 21, 35))

        temp_bmove.rectangle((0, 0, 87, 63), fill=(1, 21, 35))
        temp_bmove.rectangle((0, 64, 87, 66), fill=(187, 226, 253))
        temp_bmove.rectangle((0, 66, 87, 67), fill=(170, 220, 253))
        temp_bmove.rectangle((0, 67, 87, 109), fill=(154, 213, 252))
        temp_bmove.rectangle((0, 109, 87, 110), fill=(135, 199, 252))
        temp_bmove.rectangle((0, 110, 87, 111), fill=(120, 199, 252))
        temp_bmove.rectangle((0, 111, 87, 127), fill=(187, 226, 253))

        temp_wmove.text((1, 11), unicode(whiten), fill=(0, 0, 0), font=(None, 13))
        temp_bmove.text((1, 11), unicode(whiten), fill=(255, 255, 255), font=(None, 13))

        temp_wmove.text((1, 75), unicode(blackn), fill=(255, 255, 255), font=(None, 13))
        temp_bmove.text((1, 75), unicode(blackn), fill=(0, 0, 0), font=(None, 13))

        temp_wmove.text((14, 27), unicode(' ['+whites+']'), fill=(0, 0, 0), font=(None, 13))
        temp_bmove.text((14, 27), unicode(' ['+whites+']'), fill=(255, 255, 255), font=(None, 13))

        temp_wmove.text((14, 91), unicode(' ['+blacks+']'), fill=(255, 255, 255), font=(None, 13))
        temp_bmove.text((14, 91), unicode(' ['+blacks+']'), fill=(0, 0, 0), font=(None, 13))

        self.img_wmove = temp_wmove
        self.img_bmove = temp_bmove

        white_stone = graphics.Image.new((101, 101))
        white_stone.ellipse((6, 6, 94, 94), fill=0xffffff, outline=0, width=6)
        white_stone=white_stone.resize((12,12), keepaspect=1)

        stone_mask = graphics.Image.new((101, 101), mode='L')
        stone_mask.clear(0)
        stone_mask.ellipse((6, 6, 94, 94), fill=0xffffff, outline=0xffffff, width=6)
        stone_mask=stone_mask.resize((12,12), keepaspect=1)

        black_stone = graphics.Image.new((101, 101))
        black_stone.ellipse((6, 6, 94, 94), fill=0, outline=0xffffff,width=6)
        black_stone=black_stone.resize((12,12), keepaspect=1)

        self.img_wmove.blit(white_stone, target=(1,17), mask = stone_mask)
        self.img_wmove.blit(black_stone, target=(1,34), mask = stone_mask)
        self.img_wmove.blit(black_stone, target=(5,33), mask = stone_mask)
        self.img_wmove.blit(black_stone, target=(9,32), mask = stone_mask)

        self.img_wmove.blit(black_stone, target=(1,81), mask = stone_mask)
        self.img_wmove.blit(white_stone, target=(1,98), mask = stone_mask)
        self.img_wmove.blit(white_stone, target=(5,97), mask = stone_mask)
        self.img_wmove.blit(white_stone, target=(9,96), mask = stone_mask)

        self.img_bmove.blit(white_stone, target=(1,17), mask = stone_mask)
        self.img_bmove.blit(black_stone, target=(1,34), mask = stone_mask)
        self.img_bmove.blit(black_stone, target=(5,33), mask = stone_mask)
        self.img_bmove.blit(black_stone, target=(9,32), mask = stone_mask)

        self.img_bmove.blit(black_stone, target=(1,81), mask = stone_mask)
        self.img_bmove.blit(white_stone, target=(1,98), mask = stone_mask)
        self.img_bmove.blit(white_stone, target=(5,97), mask = stone_mask)
        self.img_bmove.blit(white_stone, target=(9,96), mask = stone_mask)

    def get(self, wmove, whitec, blackc, white_time, black_time, white_byos, black_byos, timestamp, gameover):
        if wmove:
            temp = graphics.Image.new((88, 128))
            temp.clear(0)
            temp.blit(self.img_wmove)

            temp.text((23, 43), unicode(whitec), fill=(0, 0, 0), font=(None, 13))
            temp.text((23, 107), unicode(blackc), fill=(255,255, 255), font=(None, 13))

            temp_t = time.clock()-timestamp
            if not gameover:
                temp_t = (white_time-temp_t)/60.0
            else:
                temp_t = white_time/60.0
            wsecs = int((temp_t-int(temp_t))*60.0)
            if (wsecs<10):
                wsecs = wsecs/100.0
                wsecs = str(wsecs)[2:4]
            elif wsecs == 0:
                wsecs = '00'
            else:
                wsecs = str(wsecs)
            if wsecs == '0':
                wsecs = '00'
            if temp_t>0:
                temp.text((8, 59), unicode(str(int(temp_t)) + ':' + wsecs+' ('+ str(white_byos)+')'), fill=(0,0,0), font=(None, 13, graphics.FONT_BOLD))
            else:
                temp.text((8, 59), unicode('0:00 ('+ str(white_byos)+')'), fill=(0,0,0), font=(None, 13, graphics.FONT_BOLD))

            temp_t = black_time/60.0
            bsecs = int((temp_t-int(temp_t))*60.0)
            if (bsecs<10):
                bsecs = bsecs/100.0
                bsecs = str(bsecs)[2:4]
            elif bsecs == 0:
                bsecs = '00'
            else:
                bsecs = str(bsecs)
            if bsecs == '0':
                bsecs = '00'
            if temp_t>0:
                temp.text((8, 123), unicode(str(int(temp_t)) + ':' + bsecs+' ('+ str(black_byos)+')'), fill=(255,255,255), font=(None, 13, graphics.FONT_BOLD))
            else:
                temp.text((8, 123), unicode('0:00 ('+ str(black_byos)+')'), fill=(255,255,255), font=(None, 13, graphics.FONT_BOLD))


            return temp
        else:
            temp = graphics.Image.new((88, 128))
            temp.clear(0)
            temp.blit(self.img_bmove)

            temp.text((23, 43), unicode(whitec), fill=(255,255, 255), font=(None, 13))
            temp.text((23, 107), unicode(blackc), fill=(0, 0, 0), font=(None, 13))



            temp_t = white_time/60.0
            wsecs = int((temp_t-int(temp_t))*60.0)
            if (wsecs<10):
                wsecs = wsecs/100.0
                wsecs = str(wsecs)[2:4]
            elif wsecs == 0:
                wsecs = '00'
            else:
                wsecs = str(wsecs)
            if wsecs == '0':
                wsecs = '00'
            if temp_t>0:
                temp.text((8, 59), unicode(str(int(temp_t)) + ':' + wsecs+' ('+ str(white_byos)+')'), fill=(255,255,255), font=(None, 13, graphics.FONT_BOLD))
            else:
                temp.text((8, 59), unicode('0:00 ('+ str(white_byos)+')'), fill=(255,255,255), font=(None, 13, graphics.FONT_BOLD))

            temp_t = time.clock()-timestamp

            if not gameover:
                temp_t = (black_time-temp_t)/60.0
            else:
                temp_t = black_time/60.0

            bsecs = int((temp_t-int(temp_t))*60.0)
            if (bsecs<10):
                bsecs = bsecs/100.0
                bsecs = str(bsecs)[2:4]
            elif bsecs == 0:
                bsecs = '00'
            else:
                bsecs = str(bsecs)
            if bsecs == '0':
                bsecs = '00'
            if temp_t>0:
                temp.text((8, 123), unicode(str(int(temp_t)) + ':' + bsecs+' ('+ str(black_byos)+')'), fill=(0,0,0), font=(None, 13, graphics.FONT_BOLD))
            else:
                temp.text((8, 123), unicode('0:00 ('+ str(black_byos)+')'), fill=(0,0,0), font=(None, 13, graphics.FONT_BOLD))

            return temp

class Game(object):
    def __init__(self):
        self.game_number = 0
        self.white = ''
        self.black = ''
        self.white_captures = 0
        self.black_captures = 0
        self.white_time = 0
        self.black_time = 0
        self.prevwhite_time = 0
        self.prevblack_time = 0
        self.white_byos = 0
        self.black_byos = 0
        self.prevwhite_byos = 0
        self.prevblack_byos = 0
        self.gameover = 0
        self.passcount = 0
        self.lastcolour = 'W'
        self.nextcolour = 'B'
        self.lastmovexy = (-1, -1)
        self.prevmovexy = (-1, -1)
        self.cursor = (9,9)
        self.zoom = 1.0

        self.movescrolling = 1
        self.atmove = -1
        self.scoring = 0
        self.scoringover = 0
        self.score_this = 0
        self.timestamp = time.clock()
        self.lastprocessed_movenum = -1
        self.undid = 0
        self.status = ' '
        self.gameinfo = 0
        self.yourside = 0
        self.adjourned = 0
        self.highest_move = -1

        self.sync_delay = 0

        self.app = 0
        self.igs = 0

        self.tabstatus = 'idle'
        self.komi = 0
        self.handi = 0

        self.atmove_toolow = 0
        self.completely_loaded = 0
        self.already_showed = 0
        self.playing = 0

        self.moves = ['' for i in range(2000)]

        self.board = [[' ' for i in range(19)] for j in range(19)]
        self.scoreboard = [[' ' for i in range(19)] for j in range(19)]

        self.board_moves = []
        self.board_captures = []
        self.board_score = []
        self.board_buf = [[]]

        self.gamedefimg = 0#GameDefImg(self.playing, self.handi, self.komi)
        self.gamedefimg_complete = 0
        self.gamescrollimg = 0#GameDefImg(self.playing, self.handi, self.komi)

        self.namepaneimg = 0#NamePaneImg(self.white, self.black, ' ', ' ')
        self.namepaneimg_complete = 0
        self.namepanelandscapeimg = 0#NamePaneImg(self.white, self.black, ' ', ' ')
        self.namepanelandscapeimg_complete = 0

        self.board_img = BoardView(231, 311)
        #self.board_img.init()

    def cursor_move(self):
        return self.xy2coord(self.cursor)

    def oneline(self):
        if self.gameinfo:
            temp_ws = self.gameinfo.white_strength.rstrip('*')
            temp_bs = self.gameinfo.black_strength.rstrip('*')
            return str(self.lastprocessed_movenum+1) + ' '+ self.white[0:3]+' '+temp_ws+'<'+'>'+temp_bs+' '+self.black[0:3]
        return str(self.lastprocessed_movenum+1) + ' '+ self.white[0:3]+'<'+'>'+self.black[0:3]

    def change_zoom(self):
        if self.zoom == 1.0:
            self.zoom = 1.8
        elif self.zoom == 1.8:
            self.zoom = 100.0
        elif self.zoom == 100.0:
            self.zoom = 1.0

    def cursor_up(self):
        if self.cursor[1]>0:
            self.cursor = (self.cursor[0], self.cursor[1]-1)

    def cursor_down(self):
        if self.cursor[1]<18:
            self.cursor = (self.cursor[0], self.cursor[1]+1)

    def cursor_right(self):
        if self.cursor[0]<18:
            self.cursor = (self.cursor[0]+1, self.cursor[1])

    def cursor_left(self):
        if self.cursor[0]>0:
            self.cursor = (self.cursor[0]-1, self.cursor[1])

    def getboard_image(self, length, _orient):
        self.updated = 0
        self.tabstatus = 'idle'
        if self.status == 'Game over':
            self.gameover = 1

        if not self.completely_loaded:
            return self.board_img.oldupdate(self.board, self.zoom, self.prevmovexy, self.lastmovexy, self.cursor, _orient)
        else:
            if len(self.board_buf)<=len(self.board_moves):
                temp = []
                temp.extend(self.board_buf[-1])
                temp.append(self.board_moves[len(self.board_buf)-1])
                for c in self.board_captures[len(self.board_buf)-1]:
                    temp.remove(c)
                self.board_buf.append(temp)

            if self.atmove >= len(self.board_moves)-1:
                self.atmove = len(self.board_moves)-1
                self.atmove_toolow = 0
            elif self.atmove < 0:
                self.atmove = -1
            elif self.atmove > len(self.board_buf)-2:
                self.atmove = len(self.board_buf)-2
            if self.atmove <= len(self.board_buf)-2:
                if self.atmove == len(self.board_buf)-2 and (self.scoring or (self.gameover and len(self.board_buf)==len(self.board_moves)+1)):
                    temp_moves = []
                    temp_moves.extend(self.board_buf[-1])
                    temp_moves.extend(self.board_score)
                    return self.board_img.update(temp_moves, self.zoom, self.cursor, _orient)
                return self.board_img.update(self.board_buf[self.atmove+1], self.zoom, self.cursor, _orient)
            return self.board_img.oldupdate(self.board, self.zoom, self.prevmovexy, self.lastmovexy, self.cursor, _orient)

    def getnamepane(self):
        if not self.namepaneimg_complete:
            if self.gameinfo:
                self.namepaneimg = NamePaneImg(self.white, self.black, self.gameinfo.white_strength, self.gameinfo.black_strength)
                self.namepaneimg_complete = 1
            else:
                self.namepaneimg = NamePaneImg(self.white, self.black, ' ', ' ')
        if self.nextcolour == 'W':
            return self.namepaneimg.get(1, self.white_captures, self.black_captures, self.white_time, self.black_time, self.white_byos, self.black_byos, self.timestamp, self.gameover)
        else:
            return self.namepaneimg.get(0, self.white_captures, self.black_captures, self.white_time, self.black_time, self.white_byos, self.black_byos, self.timestamp, self.gameover)

    def getnamepanelandscape(self):
        if not self.namepanelandscapeimg_complete:
            if self.gameinfo:
                self.namepanelandscapeimg = NamePaneLandscapeImg(self.white, self.black, self.gameinfo.white_strength, self.gameinfo.black_strength)
                self.namepanelandscapeimg_complete = 1
            else:
                self.namepanelandscapeimg = NamePaneLandscapeImg(self.white, self.black, ' ', ' ')
        if self.nextcolour == 'W':
            return self.namepanelandscapeimg.get(1, self.white_captures, self.black_captures, self.white_time, self.black_time, self.white_byos, self.black_byos, self.timestamp, self.gameover)
        else:
            return self.namepanelandscapeimg.get(0, self.white_captures, self.black_captures, self.white_time, self.black_time, self.white_byos, self.black_byos, self.timestamp, self.gameover)

    def getgamedefpane(self):
        if not self.gamedefimg_complete:
            if self.gameinfo:
                self.gamedefimg = GameDefImg(self.playing, self.gameinfo.handi, self.gameinfo.komi)
                self.gamedefimg_complete = 1
            else:
                self.gamedefimg = GameDefImg(self.playing, self.handi, self.komi)
        return self.gamedefimg.get()

    def getgamescrollpane(self):
        if self.handi:
            self.gamescrollimg = GameScrollImg(len(self.board_buf)-2-self.handi+1, self.atmove-self.handi+1, self.atmove_toolow)
        else:
            self.gamescrollimg = GameScrollImg(len(self.board_buf)-2, self.atmove, self.atmove_toolow)
        return self.gamescrollimg.get()

    def coord2speech(self, _coord):
        coord_dict = {'10': u'ten', '11': u'eelevan', '12': u'twelve', '13': u'thirteen', '14': u'fourteen', '15': u'fifteen', '16': u'sixteen', '17': u'seventeen', '18': u'eighteen', '19': u'nineteen'}
        if int(_coord[1:len(_coord)])>9:
            return _coord[0] + ' ' + coord_dict[_coord[1:len(_coord)]]
        return _coord[0] + ' ' + _coord[1:len(_coord)]

    def coord2xy(self, _coord):
        #~ convert (Alpha)(Number) to (x,y)
        coord_dict = {'A':0,'B':1,'C':2,'D':3,'E':4,'F':5,'G':6,'H':7,'J':8,'K':9,'L':10,'M':11,'N':12,'O':13,'P':14,'Q':15,'R':16,'S':17,'T':18}
        try:
            return coord_dict[_coord[0]], 19-int(_coord[1:len(_coord)])
        except:
            print 'Coordinate conversion failed'
            raise
            return 0

    def xy2coord(self, xy):
        #~ convert (Alpha)(Number) to (x,y)
        xy_dict = {0:'A',1:'B',2:'C',3:'D',4:'E',5:'F',6:'G',7:'H',8:'J',9:'K',10:'L',11:'M',12:'N',13:'O',14:'P',15:'Q',16:'R',17:'S',18:'T'}
        return xy_dict[xy[0]] + str(19-xy[1])

    def display(self):
        if not self.already_showed:
            temp = ''
            for y in range(19):
                for x in range(19):
                    temp += self.board[x][y]
                temp += '\r\n'
            #print self.status
            #print temp
            self.already_showed = 1

    def undoscoring(self):
        if self.gameover or self.scoring:
            self.scoreboard = [[' ' for i in range(19)] for j in range(19)]
            self.board_score = []
            temp = []
            for m in self.board_buf[-1]:
                if not m[0] == 'w' and not m[0] == 'b':
                    temp.append(m)
            self.board_buf[-1] = temp

    def undo(self, _undo_line):
        try:
            #28 pygotest1 undid the last move (A3) .

            temp = _undo_line.split(' ')
            #print temp
            if not ((temp[0] == '28') and ((temp[1] == self.white) or (temp[1] == self.black))):
                return 0

            self.moves[self.lastprocessed_movenum] = ''
            self.lastprocessed_movenum -= 1

            self.undid = 1
            self.already_showed = 0
        except:
            print 'Undo cannot be processed'
            raise
            return 0

    def addscore_line(self, _score_line):
        try:
            temp2 = _score_line.split(' ')
            temp = []
            for t in temp2:
                if len(t) > 0:
                    temp.append(t)

            if not (temp[0] == '22'):
                return 0

            if not (temp[1][-1] == ':'):
                if ((temp[1] == self.white) and (self.score_this == 0)) or ((temp[1] == self.black) and (self.score_this == 1)):
                    self.score_this += 1
                return 1

            if self.score_this == 2:
                temp3 = temp[1].split(':')

                for i in range(19):
                    if temp[2][i] == '0':
                        self.board[int(temp3[0])][i] = 'B'
                    elif temp[2][i] == '1':
                        self.board[int(temp3[0])][i] = 'W'
                    elif temp[2][i] == '4':
                        self.board[int(temp3[0])][i] = 'w'
                        self.board_score.append(('w', int(temp3[0]), i))
                    elif temp[2][i] == '5':
                        self.board[int(temp3[0])][i] = 'b'
                        self.board_score.append(('b', int(temp3[0]), i))


                if int(temp3[0]) == 18:
                    #self.display()

                    self.status = 'Game over'
                    self.already_showed = 0
            return 1
        except:
            print 'Scoring addition problem'
            raise
            return 0

    def result_line(self, _score_line):
        try:
            #20 Catal (W:O):  0.5 to pygotest2 (B:#): 358.0
            temp2 = _score_line.split(' ')
            temp = []
            for t in temp2:
                if not t == '':
                    temp.append(t)
            #print temp
            if not (temp[0] == '20'):
                return 0

            if ((temp[1] == self.white) and (temp[5] == self.black)) or ((temp[5] == self.white) and (temp[1] == self.black)):
                self.gameover = 1
                self.status = temp[1] + ': ' + temp[3] + ' ' + temp[5] + ': ' + temp[7]
                self.scoringover = 1
                if self.white == self.igs.username:
                    self.igs.sock.send('tell '+self.black+' Thank you for playing.\r\n')
                elif self.black == self.igs.username:
                    self.igs.sock.send('tell '+self.white+' Thank you for playing.\r\n')
            #print self.status
            return 1
        except:
            print 'Result process problem'
            raise
            return 0

    def addgame_line(self, _game_line):
        try:
            #15 Game 127 I: pygotest2 (0 0 -1) vs pygotest1 (0 0 -1)
            temp = _game_line.split(' ')
            if not ((temp[0] == '15') and (temp[1] == 'Game') and (int(temp[2]) == self.game_number)):
                return 0

            self.white = temp[4]
            self.white_captures = int(temp[5][1:len(temp[5])])
            #self.prevwhite_time = self.white_time
            self.prevwhite_byos = self.white_byos
            self.white_time = int(temp[6])
            self.white_byos = int(temp[7][0:-1])

            self.black = temp[9]
            self.black_captures = int(temp[10][1:len(temp[10])])
            #self.prevblack_time = self.black_time
            self.prevblack_byos = self.black_byos
            self.black_time = int(temp[11])
            self.black_byos = int(temp[12][0:-1])

            self.sync_delay = 0
            if(self.prevwhite_time != self.white_time):
                if ((self.prevwhite_byos != -1 or self.white_byos == -1) and self.prevwhite_byos != 0):
                    self.sync_delay = ((time.clock()-self.timestamp)-(self.prevwhite_time-self.white_time))
                    #print '((',time.clock(),'-',self.timestamp,')-(',self.prevwhite_time,'-',self.white_time,'))=',self.sync_delay
                self.prevwhite_time = self.white_time
                self.prevblack_time = self.black_time
                self.black_time = self.black_time - self.sync_delay

            elif(self.prevblack_time != self.black_time):
                if ((self.prevblack_byos != -1 or self.black_byos == -1) and self.prevblack_byos != 0):
                    self.sync_delay = ((time.clock()-self.timestamp)-(self.prevblack_time-self.black_time))
                    #print '((',time.clock(),'-',self.timestamp,')-(',self.prevblack_time,'-',self.black_time,'))=',self.sync_delay
                self.prevwhite_time = self.white_time
                self.prevblack_time = self.black_time
                self.white_time = self.white_time - self.sync_delay

            self.timestamp = time.clock()
            e32.reset_inactivity()
            self.updated = 1
            self.tabstatus = 'updated'
            return 1
        except:
            print 'Adding game info problem'
            raise
            return 0

    def addmove(self, _move_line):
        try:
            temp2 = _move_line.split(' ')
            temp = []
            for t in temp2:
                if len(t) > 0:
                    temp.append(t)
            #print temp
            if not (temp[0] == '15'):
                return 0

            if (temp[1] == 'Game') and (int(temp[2]) == self.game_number):
                return self.addgame_line(_move_line)

            temp3 = temp[1].split('(')
            temp = _move_line.split('): ')
            self.moves[int(temp3[0])] = temp3[1][0] + temp[1]
            if self.highest_move < int(temp3[0]):
                self.highest_move = int(temp3[0])
            #print self.moves

            #self.status = 'Got Move ' + str(len(self.moves))
            if self.undid:
                self.lastprocessed_movenum = -1
                self.undid = 0
                self.board = [[' ' for i in range(19)] for j in range(19)]
                self.board_moves = []
                self.board_captures = []
                for buf_i in range(self.handi+2):
                    if len(self.board_buf):
                        del self.board_buf[-1]
                if self.passcount > 0:
                    self.passcount -= 1
                #print 'undoing'

            while len(self.moves[self.lastprocessed_movenum+1]) > 0:
                self.lastprocessed_movenum += 1
                temp4 = self.moves[self.lastprocessed_movenum][1:len(self.moves[self.lastprocessed_movenum])].split(' ')
                #print 'temp4:',temp4
                if temp4[0] == 'Handicap':
                    self.handicap(self.moves[self.lastprocessed_movenum][0], int(temp4[1]))
                    self.handi = int(temp4[1])
                    self.atmove = len(self.board_moves)-1
                    self.status = 'Handicap '+temp4[1]
                    self.lastcolour = self.moves[self.lastprocessed_movenum][0]
                    if self.lastcolour == 'W':
                        self.nextcolour = 'B'
                    else:
                        self.nextcolour = 'W'
                    if self.lastprocessed_movenum == self.highest_move and self.app.igs.games[self.app.gui_game].game_number == self.game_number and  self.app.audio_on:
                        self.app.audiosay = u'handicap'
                    if self.nextcolour == self.yourside:
                        self.tabstatus = 'urgent'
                        if self.lastprocessed_movenum == self.highest_move and self.app.igs.games[self.app.gui_game].game_number == self.game_number and   self.app.audio_on:
                            self.app.audiosay += u'your move go'
                elif temp4[0] == 'Pass':
                    self.status = 'Pass'
                    self.passcount += 1
                    self.lastmovexy = -1, -1
                    self.lastcolour = self.moves[self.lastprocessed_movenum][0]
                    if self.lastcolour == 'W':
                        self.nextcolour = 'B'
                    else:
                        self.nextcolour = 'W'
                    if self.lastprocessed_movenum == self.highest_move and self.app.igs.games[self.app.gui_game].game_number == self.game_number and   self.app.audio_on:
                            self.app.audiosay = u'pass'
                    if self.nextcolour == self.yourside:
                        self.tabstatus = 'urgent'

                    if self.passcount == 3:
                        self.gameover = 1
                        self.status = 'Game over'
                        if self.lastprocessed_movenum == self.highest_move and self.app.igs.games[self.app.gui_game].game_number == self.game_number and   self.app.audio_on and self.nextcolour == self.yourside:
                            self.app.audiosay  += u'mark dead groups'
                    elif self.lastprocessed_movenum == self.highest_move and self.app.igs.games[self.app.gui_game].game_number == self.game_number and   self.app.audio_on and self.nextcolour == self.yourside:
                        self.app.audiosay += u'your move go'
                else:
                    self.status = 'Move ' + str(self.lastprocessed_movenum+1) + ': ' + temp4[0]

                    self.board_captures.append([])
                    for t in temp4[1:len(temp4)]:
                        #print 'taking', t
                        self.takestone(self.moves[self.lastprocessed_movenum][0], t)

                    self.addstone(self.moves[self.lastprocessed_movenum][0], temp4[0])

                    if not self.completely_loaded:
                        self.atmove = len(self.board_moves)-1
                    if self.atmove == len(self.board_moves)-2:
                        self.atmove = len(self.board_moves)-1
                        self.atmove_toolow = 0
                    else:
                        self.atmove_toolow = 1
                    if self.lastprocessed_movenum == self.highest_move and self.app.igs.games[self.app.gui_game].game_number == self.game_number and   self.app.audio_on:
                        self.app.audiosay = unicode(self.coord2speech(temp4[0]))
                        if len(temp4[1:len(temp4)]) == 1:
                            self.app.audiosay += u'capturing one stone'
                        elif len(temp4[1:len(temp4)]) > 1:
                            self.app.audiosay += u'capturing ' + unicode(str(len(temp4[1:len(temp4)]))) + u' stones'
                    if self.nextcolour == self.yourside:
                        self.tabstatus = 'urgent'
                        if self.lastprocessed_movenum == self.highest_move and self.app.igs.games[self.app.gui_game].game_number == self.game_number and   self.app.audio_on:
                            self.app.audiosay += u'your move go'


            self.already_showed = 0
            if self.gameinfo and self.lastprocessed_movenum >= self.gameinfo.moves_played -1:
                self.completely_loaded = 1
            return 1
        except:
            print 'Move addition failed'
            raise
            return 0

    def addstone(self, _colour, _move):
        try:
            x, y = self.coord2xy(_move)
            self.board[x][y] = _colour

            self.board_moves.append((_colour, x, y))

            self.passcount = 0
            self.lastcolour = _colour
            self.prevmovexy = self.lastmovexy
            self.lastmovexy = x, y
            self.board_img.view_center = self.lastmovexy
            if _colour == 'W':
                self.nextcolour = 'B'
            else:
                self.nextcolour = 'W'
            return 1
        except:
            print 'Stone addition failed'
            raise
            return 0

    def takestone(self, _colour, _move):
        try:
            x, y = self.coord2xy(_move)
            self.board[x][y] = ' '

            if _colour == 'B':
                self.board_captures[-1].append(('W', x, y))
                #print len(self.board_captures[-1]),
            else:
                self.board_captures[-1].append(('B', x, y))
                #print len(self.board_captures[-1]),

            return 1
        except:
            print 'Stone removal failed'
            raise
            return 0

    def handicap(self, _colour, _amount):
        hc = ['Q16', 'D4', 'D16', 'Q4', 'K10']
        hc2 = ['Q16', 'D4', 'D16', 'Q4', 'D10', 'Q10', 'K10']
        hc3 = ['Q16', 'D4', 'D16', 'Q4', 'D10', 'Q10', 'K4', 'K16', 'K10']
        try:
            if _amount>=2 and _amount<6:
                for i in range(0, _amount):
                    self.board_captures.append([])
                    self.addstone(_colour, hc[i])
            elif _amount>=6 and _amount<8:
                for i in range(0, _amount):
                    self.board_captures.append([])
                    self.addstone(_colour, hc2[i])
            elif _amount>=8 and _amount<10:
                for i in range(0, _amount):
                    self.board_captures.append([])
                    self.addstone(_colour, hc3[i])
            return 1
        except:
            print 'Handicap failed'
            raise
            return 0

    def remove_group(self, _position, _position_colour=0):
        x, y = self.coord2xy(_position)
        #print _position
        colour = _position_colour
        if _position_colour==0:
            colour = self.board[x][y][0]

        current_list = [(x,y)]
        while len(current_list):
            new_list = []
            for x,y in current_list:
                if x>0:
                    if (self.scoreboard[x-1][y][0] == ' ') and ((self.board[x-1][y][0] == ' ') or (self.board[x-1][y][0] == colour)):
                        if colour == 'W':
                            self.scoreboard[x-1][y] = 'b'
                            self.board_score.append(('b', x-1, y))
                        else:
                            self.scoreboard[x-1][y] = 'w'
                            self.board_score.append(('w', x-1, y))
                        new_list.append((x-1, y))
                if x<18:
                    if (self.scoreboard[x+1][y][0] == ' ') and ((self.board[x+1][y][0] == ' ') or (self.board[x+1][y][0] == colour)):
                        if colour == 'W':
                            self.scoreboard[x+1][y] = 'b'
                            self.board_score.append(('b', x+1, y))
                        else:
                            self.scoreboard[x+1][y] = 'w'
                            self.board_score.append(('w', x+1, y))
                        new_list.append((x+1, y))
                if y>0:
                    if (self.scoreboard[x][y-1][0] == ' ') and ((self.board[x][y-1][0] == ' ') or (self.board[x][y-1][0] == colour)):
                        if colour == 'W':
                            self.scoreboard[x][y-1] = 'b'
                            self.board_score.append(('b', x, y-1))
                        else:
                            self.scoreboard[x][y-1] = 'w'
                            self.board_score.append(('w', x, y-1))
                        new_list.append((x, y-1))
                if y<18:
                    if (self.scoreboard[x][y+1][0] == ' ') and ((self.board[x][y+1][0] == ' ') or (self.board[x][y+1][0] == colour)):
                        if colour == 'W':
                            self.scoreboard[x][y+1] = 'b'
                            self.board_score.append(('b', x, y+1))
                        else:
                            self.scoreboard[x][y+1] = 'w'
                            self.board_score.append(('w', x, y+1))
                        new_list.append((x, y+1))
            current_list = []
            current_list.extend(new_list)

class IGS:
    def __init__(self, _app, _username, _password, _apid):
        self.app = _app

        self.username = _username
        self.password = _password
        self.apid = _apid
        self.sock = SocketProxy(('igs.joyjoy.net', 6969), self.apid, self.app)
        self.sock.app = self.app
        self.storage = 0
        self.stored = []
        self.gameinfo = []
        self.games = []
        self.playerinfo = []
        self.info_begin = 0
        self.info_end = 0

        self.closedlist = []
        self.playerinfo_end = 0

        self.moving = 0
        self.current_game = 0
        self.stop_var = 0
        self.logged_in = 0
        self.found = 0
        self.removed = -1
        self.games_access = 0
        self.requests = 0

        self.playinggames = 0
        self.observedgames = 0
        self.recv_buf = ''

        thread.start_new_thread(self.receive_thread, ())

    def stop(self):
        self.sock.stop()
        self.stop_var = 1
        #self.storage.Close()

    def playerinfo_line(self, _line): #27 who line
        #27                 ******** 1276 Players 340 Total Games ********
        temp2 = _line.split(' ')
        temp = []
        for t in temp2:
            if len(t) > 0:
                temp.append(t)

        if temp[1] == '********':
            self.playerinfo_end = 1

        if not (temp[0] == '27') or (temp[1] == 'Info') or (temp[1] == '********'):
            return 0

        split_index = temp.index('|')
        players = [temp[1:split_index]]
        if (len(temp)>split_index+1):
            players.append(temp[split_index+1:len(temp)])

        player_stats = []
        for p in players:

            player_stats.append(PlayerInfo())
            try:
                touching = 0
                p_index = 0
                for c in p[p_index]:
                    if c == 'Q':
                        player_stats[-1].quiet_on = 1
                    elif c == 'S':
                        player_stats[-1].shout_off = 1
                    elif c == 'X':
                        player_stats[-1].open_off = 1
                    elif c == '!':
                        player_stats[-1].looking_on = 1
                    else:
                        break
                    touching += 1

                if touching == 0:
                    if not p[0] == '--':
                        player_stats[-1].observenumber = int(p[p_index])
                    p_index = 0

                elif touching<len(p[p_index]):
                    player_stats[-1].observenumber = int(p[p_index][touching:len(p[p_index])])
                    p_index = 0

                else:
                    p_index = 1
                    if not p[1] == '--':
                        player_stats[-1].observenumber = int(p[p_index])


                p_index += 1
                if not p[p_index] == '--':
                    player_stats[-1].game_number = int(p[p_index])

                p_index += 1
                player_stats[-1].name = p[p_index]

                p_index += 1
                player_stats[-1].idle = p[p_index]

                p_index += 1
                player_stats[-1].strength = p[p_index]
                #player_stats[-1].display()
            except:
                del player_stats[-1]
                print 'Player addition error'

        #for pl in player_stats:
        #    pl.display()

        return player_stats

    def gameinfo_line(self, _line): #7
        temp2 = _line.split(']')
        #print temp2

        temp = temp2[0].split('[')

        if not (temp[0] == '7 ') or (temp[1] == '##'):
            return 0

        gameinfo = GameInfo()
        gameinfo.game_number = int(temp[1])

        temp = temp2[1].split('[')
        gameinfo.white_name = temp[0].rstrip(' ').lstrip(' ')
        gameinfo.white_strength = temp[1].rstrip(' ').lstrip(' ')

        temp = temp2[2].split('[')
        temp3 = temp[0].split('.')
        gameinfo.black_name = temp3[1].rstrip(' ').lstrip(' ')
        gameinfo.black_strength = temp[1].rstrip(' ').lstrip(' ')

        temp = temp2[3].replace('(',' ').replace(')',' ')
        temp = temp.split(' ')

        temp3 = []
        for t in temp:
            if len(t) > 0:
                temp3.append(t)

        gameinfo.moves_played = int(temp3[0])
        gameinfo.size = int(temp3[1])
        gameinfo.handi = int(temp3[2])
        gameinfo.komi = float(temp3[3])
        gameinfo.BY = int(temp3[4])
        gameinfo.FR = temp3[5]
        gameinfo.last_column = temp3[6]

        #gameinfo.display()

        return gameinfo

    def receive_thread(self):
        while not self.stop_var:
            try:
                self.recv_buf += self.sock.recv()
                #print self.recv_buf
                if self.recv_buf[len(self.recv_buf)-7:len(self.recv_buf)] == 'Login: ':
                    self.recv_buf += '\r\n'
                    #print self.recv_buf[len(self.recv_buf)-7-2:len(self.recv_buf)-2]
                    #print self.recv_buf.split('\r\n')
                elif self.recv_buf[len(self.recv_buf)-10:len(self.recv_buf)] == 'Password: ':
                    self.recv_buf += '\r\n'
                elif self.recv_buf[len(self.recv_buf)-3:len(self.recv_buf)] == '#> ':
                    self.recv_buf += '\r\n'
                temp = self.recv_buf.split('\r\n')
                if (len(temp) > 1):

                    #print temp
                    self.recv_buf = self.recv_buf[len(temp[0])+2:len(self.recv_buf)]
                    if (len(temp[0])>0):
                        #self.app.notification = temp[0]
                        self.process_line(temp[0])

                e32.ao_yield()
                #~ print 'rt',
            except:
                print 'Receive thread error'
                raise

    def process_line(self, _linet):
        try:
            _line = _linet
            if (_line[0:3] == '\xff\xfb\x01') or (_line[0:3] == '\xff\xfc\x01'):
                _line = _line[3:len(_line)]
            if len(_line) == 0:
                return 1

            if _line[0:20] == 'Your account name is':
                #Your account name is guest7766.
                self.app.username = _line[21:len(_line)-1]
                self.username = _line[21:len(_line)-1]

            temp = _line[0:2].rstrip(' ')

            if temp == '1':
                if _line == '1 1':
                    self.sock.send(self.password+'\r\n')
                elif _line == '1 5':
                    self.requests -= 1
                    if self.info_begin:
                        self.info_end = 1

            elif temp == '5':
                if not self.logged_in:
                    #print 'Invalid password'
                    self.app.notification = 'Invalid password'
                #5 The player pygotest1 is not on currently.
                temp2 = _line.split(' ')
                if (temp2[1] == 'The') and (temp2[2] == 'player') and (len(temp2)>7) and (temp2[7] == 'currently.'):
                    self.found = 1

            elif temp == '7':
                gi_temp = self.gameinfo_line(_line)
                if gi_temp:
                    already_there = 0
                    for g in self.gameinfo:
                        if (gi_temp.game_number == g.game_number):
                            already_there = 1
                    if not already_there:
                        self.gameinfo.append(gi_temp)
                        self.games_access = 1
                        for i in self.games:
                            if i.game_number == self.gameinfo[-1].game_number:
                                i.gameinfo = copy.deepcopy(self.gameinfo[-1])
                        self.games_access = 0
                self.info_begin = 1
                self.info_end = 0

            elif temp == '9':
                #9 {Game 224: Beyond vs ddmen : White forfeits on time.}
                #9 Game 34: lazer vs hhk1 has adjourned.
                #9 Game 619: fire vs musashi has adjourned.
                #9 Match [245] with pygotest1 in 10 accepted.
                #9 Creating match [58] with pygotest2.

                #9 Game has been adjourned.
                #9 Your opponent has lost his/her connection.
                #9 You win the game with Catal by 1-times disconnection.

                temp2 = _line.split('{')
                if len(temp2)>1:
                    temp2 = _line.split(':')
                    #print temp2[2][0:len(temp2[2])-2]
                    temp3 = temp2[0].split(' ')
                    self.games_access = 1
                    for g in self.games:
                        if g.game_number == int(temp3[2]):
                            g.gameover = 1
                            g.status = temp2[2][1:len(temp2[2])-2]
                    self.games_access = 0
                temp2 = _line.split(' ')
                if len(temp2)>7 and temp2[1] == 'Game' and temp2[7] == 'adjourned.':
                    temp3 = 0
                    try:
                        temp3 = int(temp2[2][0:len(temp2[2])-1])
                    except:
                        pass
                    if temp3>0:
                        self.games_access = 1
                        for g in self.games:
                            if g.game_number == temp3:
                                g.gameover = 1
                                adjourn_temp = _line.split(':')
                                g.status = adjourn_temp[1]
                                self.app.notification = adjourn_temp[1]
                        self.games_access = 0
                elif len(temp2)>4 and temp2[1] == 'Game' and temp2[4] == 'adjourned.':
                    self.app.notification = 'Game adjourned'
                    if self.app.gui_game>-1 and len(self.games):
                        self.games[self.app.gui_game].status = 'Game adjourned'
                elif len(temp2)>11 and temp2[2] == 'lost' and temp2[3] == 'the' and temp2[4] == 'game' and temp2[6] == 'due' and temp2[8] == 'no-move.':
                    #9 pygotest1 lost the game 878 due to no-move. move 0 points.
                    for g in self.games:
                        if g.game_number == int(temp2[5]):
                            g.gameover = 1
                            g.status = 'Game over [no move in 1 min]'
                elif len(temp2)>6 and temp2[1] == 'Removing' and temp2[2] == 'game' and temp2[4] == 'from' and temp2[5] == 'observation':
                    #9 Removing game 11 from observation list.
                    for g in self.games:
                        if g.game_number == int(temp2[3]):
                            g.gameover = 1
                            g.status = 'Game over [removed]'
                elif len(temp2)>5 and temp2[2] == 'has' and temp2[3] == 'resigned' and temp2[4] == 'the' and temp2[5] == 'game.':
                    #9 Catal has resigned the game.
                    #9 pygotest2 has resigned the game.
                    self.app.notification = _line[2:len(_line)]
                    if self.app.gui_game>-1 and len(self.games):
                        self.games[self.app.gui_game].status = _line[2:len(_line)]
                elif len(temp2)>6 and temp2[2] == 'has' and temp2[3] == 'run' and temp2[4] == 'out' and temp2[5] == 'of' and temp2[6] == 'time.':
                    #9 pygotest1 has run out of time.
                    self.app.notification = _line[2:len(_line)]
                    if self.app.gui_game>-1 and len(self.games):
                        self.games[self.app.gui_game].status = _line[2:len(_line)]
                elif len(temp2)>7 and temp2[2] == 'wants' and temp2[3] == 'the' and temp2[4] == 'komi':
                    #9 Catal wants the komi to be  5.5
                    if not temp2[1] == self.username:
                        while self.app.get_komi:
                            e32.ao_yield()
                        self.app.get_komi = _line[2:len(_line)]
                        while self.app.get_komi:
                            e32.ao_yield()
                        if self.app.allow_komi:
                            #print 'komi '+temp2[8]+'\r\n'
                            self.sock.send('komi '+temp2[8]+'\r\n')
                            self.app.notification = 'Komi set to '+temp2[8]
                            if self.app.gui_game>-1 and len(self.games):
                                self.games[self.app.gui_game].status = 'Komi set to '+temp2[8]
                        else:
                            self.app.notification = 'Komi ignored'
                            if self.app.gui_game>-1 and len(self.games):
                                self.games[self.app.gui_game].status = 'Komi ignored'

                elif len(temp2)>12 and temp2[1] == 'Use' and temp2[2] == '<match' and temp2[12] == 'respond.':
                    #9 Use <match lakok W 19 1 10> or <decline lakok> to respond.
                    while self.app.get_offer:
                        e32.ao_yield()
                    self.app.get_offer_content[0] = 'Play with '+ temp2[3]+' ['+temp2[4]+' '+temp2[5]+' '+temp2[6]+' '+temp2[7][0:-1]+']'
                    self.app.get_offer_content[1] = 'match '+temp2[3]+' '+temp2[4]+' '+temp2[5]+' '+temp2[6]+' '+temp2[7][0:-1]+'\r\n'
                    self.app.get_offer_content[2] = 'decline '+temp2[3]+'\r\n'
                    self.app.get_offer = 1

                elif (temp2[1] == 'Match') and (temp2[4] == 'declined.'):
                    #9 pygotest1 declines your request for a match.
                    #9 Match with pygotest1 declined.
                    self.app.notification = temp2[3] + ' declined to play'
                    if self.app.gui_game>-1 and len(self.games):
                        self.games[self.app.gui_game].status = temp2[3] + ' declined to play'
                elif (temp2[1] == 'Match') and (temp2[7] == 'accepted.'):
                    #~ self.playinggames += 1
                    self.games_access = 1
                    for g in self.games:
                        if g.game_number == int(temp2[2][1:-1]):
                            g.playing = 1
                            g.movescrolling = 0
                            if g.white == self.username:
                                g.yourside = 'W'
                            elif g.black == self.username:
                                g.yourside = 'B'
                    self.games_access = 0

                elif (temp2[1] == 'Removing') and (temp2[2] == 'game') and (temp2[5] == 'observation'):
                    self.removed = int(temp2[3])
                elif len(temp2)>6 and temp2[4] == 'lost' and temp2[6] == 'connection.':
                    self.app.notification = 'Your opponent has disconnected'
                    if self.app.gui_game>-1 and len(self.games):
                        self.games[self.app.gui_game].status = 'Your opponent has disconnected'
                elif len(temp2)>6 and temp2[1] == 'Removed' and temp2[2] == 'game' and temp2[3] == 'file' and temp2[5] == 'from' and temp2[6] == 'database.':
                    self.app.notification = 'Game deleted'
                    temp_names = temp2[4].split('-')
                    if self.username == temp_names[0]:
                        self.sock.send('tell '+temp_names[1]+' Thank you for playing.\r\n')
                    elif self.username == temp_names[1]:
                        self.sock.send('tell '+temp_names[0]+' Thank you for playing.\r\n')
                    #if self.app.gui_game>-1 and len(self.games):
                    #    self.games[self.app.gui_game].status = 'Game deleted'
                    #9 Removed game file pygotest2-pygotest1 from database.
                elif len(temp2)>11 and temp2[1] == 'Board' and temp2[3]=='restored' and temp2[10]=='started' and temp2[11]=='scoring':
                    #9 Board is restored to what it was when you started scoring
                    self.games_access = 1
                    for g in self.games:
                        g.undoscoring()
                    self.games_access = 0

            elif temp == '15':
                temp2 = _line.split(' ')
                temp3 = []
                for t in temp2:
                    if len(t) > 0:
                        temp3.append(t)

                if (temp3[0] == '15') and (temp3[1] == 'Game'):
                    self.current_game = int(temp3[2])

                found = 0
                i = 0
                self.games_access = 1
                for g in self.games:
                    i+=1
                    if g.game_number == self.current_game:
                        g.addmove(_line)
                        if self.app.autoswitch:
                            self.app.gui_game = i-1

                        found = 1

                for i in range(len(self.closedlist)):
                    if self.closedlist[i] == self.current_game:
                        found = 1
                        break

                if not found:
                    self.games.append(Game())
                    self.games[-1].game_number = self.current_game

                    self.games[-1].addmove(_line)
                    self.games[-1].app = self.app
                    self.games[-1].igs = self

                    found = 0
                    for i in self.gameinfo:
                        if i.game_number == self.current_game:
                            self.games[-1].gameinfo = copy.deepcopy(i)
                            found = 1

                    if not found:
                        #15 Game 127 I: pygotest2 (0 0 -1) vs pygotest1 (0 0 -1)
                        self.sock.send('games '+str(self.current_game) + '\r\n')

                    if (self.games[-1].white == self.username) or (self.games[-1].black == self.username):
                        #~ #15 Game 127 I: pygotest2 (0 0 -1) vs pygotest1 (0 0 -1)
                        self.sock.send('moves ' + str(self.current_game) + '\r\n')

                        self.games[-1].playing = 1
                        self.games[-1].movescrolling = 0

                        self.playinggames = 0
                        for g in self.games:
                            if g.playing and not g.gameover:
                                self.playinggames += 1

                        if self.games[-1].white == self.username:
                            self.games[-1].yourside = 'W'
                        elif self.games[-1].black == self.username:
                            self.games[-1].yourside = 'B'
                        if (self.playinggames == 1):
                            self.sock.send('say Hi! Thank you for playing. (Automated message, get IGS for Nokia Symbian now at http://pandapy.googlecode.com ) \r\n')# from http://pandapy.googlecode.com , IGS for Nokia, get it now!
                        elif (self.playinggames > 1):
                            self.sock.send('say '+temp2[2][1:-1]+ ' Hi! Thank you for playing. (Automated message, get IGS for Nokia Symbian now at http://pandapy.googlecode.com ) \r\n')

                    #if self.app.autoswitch:
                    self.app.gui_game = len(self.games)-1

                self.games_access = 0

            elif temp == '18':
                #18 Catal-pygotest1       pygotest1-pygotest2
                #18 Found 2 stored games.

                #18 Found 0 stored games.

                temp2 = _line.split(' ')
                temp3 = []
                for t in temp2:
                    if len(t) > 0:
                        temp3.append(t)

                if not (temp3[1] == 'Found'):
                    for t in temp3[1:len(temp3)]:
                        self.stored.append(unicode(t))
                else:
                    self.logged_in = 1
            elif temp == '20':
                #20 Catal (W:O):  0.5 to pygotest2 (B:#): 358.0
                self.playinggames -= 1
                self.games_access = 1
                for g in self.games:
                    g.result_line(_line)
                self.games_access = 0
            elif temp == '22':
                self.games_access = 1
                for g in self.games:
                    g.addscore_line(_line)
                self.games_access = 0

            elif temp == '24':
                #24 *SYSTEM*: pygotest2 requests undo.
                #24 *SYSTEM*: Please wait for your opponent to restart the game for 5 minutes.
                temp2 = _line.split(' ')
                self.games_access = 1
                for g in self.games:
                    if ((temp2[1]=='*SYSTEM*:') and (temp2[4]=='undo.')) and ((temp2[2] == g.white) or (temp2[2] == g.black)):
                        self.app.get_undo = 1
                        while self.app.get_undo:
                            e32.ao_yield()
                        if self.app.allow_undo:
                            self.sock.send('undo '+str(g.game_number)+'\r\n')
                            g.status = 'Undo granted'
                        else:
                            self.sock.send('noundo '+str(g.game_number)+'\r\n')
                            g.status = 'Undo denied'
                self.games_access = 0
            elif temp == '27':
                pi_temp = self.playerinfo_line(_line)
                if pi_temp:
                    for p in pi_temp:
                        self.playerinfo.append(p)
                self.info_begin = 1
                self.info_end = 0

            elif temp == '28':
                #28 pygotest1 undid the last move (A3) .
                self.games_access = 1
                for g in self.games:
                    g.undo(_line)
                self.games_access = 0

            elif temp == '36':
                #36 Catal wants a match with you:
                #36 Catal wants 19x19 in 90 minutes with 10 byo-yomi and 25 byo-stones
                #36 To accept match type 'automatch Catal'
                temp2 = _line.split(' ')
                if len(temp2)>12 and temp2[2] == 'wants' and temp2[4] == 'in' and temp2[7] == 'with' and temp2[9] == 'byo-yomi' and not self.app.username == temp2[1]:
                    while self.app.get_offer:
                        e32.ao_yield()
                    self.app.get_offer_content[0] = 'Automatch with '+ temp2[1]+' ['+temp2[3]+' '+temp2[5]+' '+temp2[8]+' '+temp2[11]+']'
                    self.app.get_offer_content[1] = 'automatch '+temp2[1]+'\r\n'
                    self.app.get_offer_content[2] = ''
                    self.app.get_offer = 1
            elif temp == '39':
                self.app.notification = 'Welcome '+self.username+'. Loading settings ...'
                self.requests += 1
                self.sock.send('toggle client true\r\n')
                self.requests += 1
                self.sock.send('toggle quiet true\r\n')
                self.requests += 1
                self.sock.send('toggle singlegame true\r\n')
                self.requests += 1
                self.sock.send('toggle verbose false\r\n')
                self.requests += 1
                self.sock.send('toggle newundo true\r\n')
                self.requests += 1
                self.sock.send('toggle bell false\r\n')
                self.requests += 1
                self.sock.send('toggle open false\r\n')
                self.requests += 1
                self.sock.send('toggle looking false\r\n')
                self.requests += 1
                self.sock.send('toggle chatter false\r\n')
                self.requests += 1
                self.sock.send('toggle kibitz false\r\n')
                self.requests += 1
                self.sock.send('toggle shout false\r\n')
                self.requests += 1
                self.stored = []
                self.sock.send('stored\r\n')
            elif temp == '48':
                #48 Game 84 has been adjourned by pygotest2
                #48 Game 302 pygotest1 requests an adjournment
                temp2 = _line.split(' ')
                temp3 = []
                for t in temp2:
                    if len(t) > 0:
                        temp3.append(t)
                if len(temp3)>6 and temp3[4] == 'requests' and temp3[6] == 'adjournment':
                    if (self.playinggames == 1):
                        self.sock.send('adjourn\r\n')
                        for g in self.games:
                            if g.game_number == int(temp3[2]):
                                g.adjourned = 1
                                g.status = 'Game adjourned'
                    elif (self.playinggames > 1):
                        self.sock.send('adjourn ' +temp3[2] +'\r\n')
                        for g in self.games:
                            if g.game_number == int(temp3[2]):
                                g.adjourned = 1
                                g.status = 'Game adjourned'
                elif len(temp3)>7 and temp3[5] == 'adjourned':
                    self.app.notification = temp3[7] + ' adjourned game'
                    if self.app.gui_game>-1 and len(self.games):
                        self.games[self.app.gui_game].status = temp3[7] + ' adjourned game'
                    for g in self.games:
                        if g.game_number == int(temp3[2]):
                            g.adjourned = 1
                            g.status = 'Game adjourned'
            elif temp == '49':
                #49 Game 54 Catal is removing @ B1
                temp2 = _line.split(' ')
                self.games_access = 1
                for g in self.games:
                    if g.game_number == int(temp2[2]):
                        g.remove_group(temp2[7])
                        g.scoring = 1
                self.games_access = 0
            #~ elif temp == '51':
                #~ #51 Say in game 797
                #~ temp2 = _line.split(' ')
                #~ if (temp2[1] == 'Say'):
                    #~ self.playinggames += 1
                    #~ for g in self.games:
                        #~ if g.game_number == int(temp2[4]):
                            #~ g.playing = 1
                #~ if (temp2[1] == 'Say') and (self.playinggames == 1):
                    #~ self.sock.send('say Hi! Thank you for playing. (Automated message , IGS for Nokia, get it now!) \r\n')
                #~ elif (temp2[1] == 'Say') and (self.playinggames > 1):
                    #~ self.sock.send('say '+temp2[4]+ ' Hi! Thank you for playing. (Automated message  , IGS for Nokia, get it now!) \r\n')
            else:
                if _line == 'Login: ':
                    self.stored = []
                    self.gameinfo = []
                    self.games = []
                    self.playerinfo = []
                    self.info_begin = 0
                    self.info_end = 0

                    self.moving = 0
                    self.current_game = 0
                    self.stop_var = 0
                    self.logged_in = 0
                    self.found = 0

                    self.requests = 0

                    self.playinggames = 0
                    self.observedgames = 0
                    self.recv_buf = ''
                    self.app.notification = self.username+' is logging in ...'
                    self.sock.send(self.username+'\r\n')
                elif _line == 'Password: ':
                    self.sock.send(self.password+'\r\n')
                elif _line == 'sorry.':
                    print 'Server not taking connections'
                    self.app.notification = 'Server not taking connections'
                elif _line[len(_line)-3:len(_line)] == '#> ':
                    self.requests += 1
                    self.sock.send('toggle client true\r\n')
                    self.requests += 1
                    self.sock.send('toggle quiet true\r\n')
                    self.requests += 1
                    self.sock.send('toggle singlegame true\r\n')
                    self.requests += 1
                    self.sock.send('toggle verbose false\r\n')
                    self.requests += 1
                    self.sock.send('toggle newundo true\r\n')
                    self.requests += 1
                    self.sock.send('toggle bell false\r\n')
                    self.requests += 1
                    self.sock.send('toggle open false\r\n')
                    self.requests += 1
                    self.sock.send('toggle looking false\r\n')
                    self.requests += 1
                    self.sock.send('toggle chatter false\r\n')
                    self.requests += 1
                    self.sock.send('toggle kibitz false\r\n')
                    self.requests += 1
                    self.sock.send('toggle shout false\r\n')

                    if len(self.app.username)>6 and self.app.username[0:5] == 'guest':
                        self.logged_in = 1
                        self.stored = []
                    else:
                        self.requests += 1
                        self.stored = []
                        self.sock.send('stored\r\n')

        except:
            print 'Process line error'
            raise
            return 0

    def move_input(self, __move = 0):
        _move = __move
        self.moving = 1
        self.games_access = 1
        #print len(self.games), self.games[self.app.gui_game].playing, self.app.gui_game
        if (len(self.games)>0) and (self.games[self.app.gui_game].playing):
            if not _move:
                _move = self.games[self.app.gui_game].cursor_move()
                #print _move
            if (self.playinggames == 1):
                self.sock.send(_move+'\r\n')
            else:
                self.sock.send(_move+' '+str(self.games[self.app.gui_game].game_number)+'\r\n')
        self.moving = 0
        self.games_access = 0

    def who_command(self, _spec, __thread=0):
        self.playerinfo = []
        while not self.logged_in:
            pass
            e32.ao_yield()
        self.playerinfo_end = 0

        self.sock.send('who '+_spec+'\r\n')
        temp = 0
        while not self.playerinfo_end:
            if not len(self.playerinfo) == temp:
                temp = len(self.playerinfo)
            #self.app.do_topline()
            self.app.notification = unicode(str(temp) + ' players found ')
            #+ str(self.info_begin)+str(self.info_end)+str(temp2))
            #self.app.redraw()
            e32.ao_yield()
        if __thread == 1:
            self.app.get_play = 1
        elif __thread == 2:
            self.app.get_automatch = 1

    def get_observed_games(self):
        self.gameinfo = []
        while not self.logged_in:
            pass
            e32.ao_yield()
        for p in self.playerinfo:
            if p.game_number > 0:
                self.info_end = 0
                self.info_begin = 0
                self.sock.send('games '+str(p.game_number) + '\r\n')
                found = 0
                temp = 0
                for i in self.gameinfo:
                    if i.game_number == p.game_number:
                        found = 1
                while not found and temp<1000:
                    for i in self.gameinfo:
                        if i.game_number == p.game_number:
                            found = 1
                    e32.ao_yield()
                    temp += 1

                self.app.notification = unicode(str(len(self.gameinfo)) + ' games found')

        self.app.get_observed = 1

    def start_observe(self, _index):
        while not self.logged_in:
            pass
            e32.ao_yield()
        for i in range(len(self.closedlist)):
            if self.closedlist[i] == self.gameinfo[_index].game_number:
                del self.closedlist[i]
                break
        for g in self.games:
            if g.game_number == self.gameinfo[_index].game_number:
                return
        self.games_access = 1
        self.sock.send('observe ' + str(self.gameinfo[_index].game_number) + '\r\n')
        self.sock.send('moves ' + str(self.gameinfo[_index].game_number) + '\r\n')
        self.games_access = 0

    def request_game(self, _name, (_colour, _maintime, _byotime)):
        while not self.logged_in:
            pass
            e32.ao_yield()
        self.games_access = 1
        if len(self.games)<8:
            self.sock.send('match '+_name+' '+_colour+' 19 '+_maintime+' '+_byotime+'\r\n')
        self.games_access = 0
    def load_game(self, _title):
        while not self.logged_in:
            pass
            e32.ao_yield()
        self.sock.send('load '+ _title + '\r\n')
        self.app.notification = 'Loading game'
        #self.app.redraw()

class TabsPaneImg(object):
    def __init__(self):
        self.img = graphics.Image.new((100, 13))
    def get(self, games_status):
        self.img = graphics.Image.new((100, 13))
        self.img.clear(0)

        i = 0
        for s in games_status[0:9]:
            if s == 'idle':
                self.img.text((2+10*i,10), unicode(str(i+1)), fill=(0, 80, 255), font=(None, 10, graphics.FONT_BOLD))
            elif s == 'current':
                self.img.rectangle((1+10*i,0,10*i+9, 13), fill=(180, 187, 140))
                self.img.text((2+10*i,10), unicode(str(i+1)), fill=(0, 0, 0), font=(None, 10, graphics.FONT_BOLD))
            elif s == 'urgent':
                self.img.text((2+10*i,10), unicode(str(i+1)), fill=(255, 80,0), font=(None, 10, graphics.FONT_BOLD))
            elif s == 'updated':
                self.img.text((2+10*i,10), unicode(str(i+1)), fill=(0, 255, 80), font=(None, 10, graphics.FONT_BOLD))
            i += 1
        return self.img

class Application(object):
    def __init__(self):
        try:
            appuifw.app.title = u'PandaPy\nLoading client'
            appuifw.app.screen = 'normal'

            self.lock = e32.Ao_lock()
            self.locked = 0
            appuifw.app.exit_key_handler = self.quit
            sys.exitfunc = self.myexitfunc
            self.igs = 0



            self.storage = PersistentStorage("c:\\Python\\pandapy")
            self.name = 'PandaPy'

            self.apid = self.storage.GetValue('apid')
            while self.apid == None:
                self.menu_apidsetting_do()


            self.helping = 0

            self.observeparams = ''
            self.get_undo = 0
            self.get_offer = 0
            self.get_offer_content = ['','','']
            self.get_komi = 0
            self.allow_komi = 0
            self.allow_undo = 1
            self.blitz_on = 0
            self.blitz_def = 0
            self.menu_blitz = (unicode('Watch blitz'), self.menu_blitz_do)
            self.audio_on = 0
            self.audiosay = u''
            self.menu_speech = (unicode('Speech'), self.menu_speech_do)
            self.singlegame = 0
            self.menu_singlegame = (unicode('Singlegame'), self.menu_singlegame_do)
            self.open = 0
            self.menu_open = (unicode('Open'), self.menu_open_do)

            self.downscrolljumps = self.storage.GetValue('downscrolljumps')
            if self.downscrolljumps == None:
                self.downscrolljumps = 10
            else:
                self.downscrolljumps = int(self.downscrolljumps)
            self.menu_movescrolling = (unicode('Moving mode'), self.menu_movescrolling_do)

            self.automatchsettings = [(u'Opponent range', 'text', u''), (u'Size', 'text', u''),  (u'Main Time', 'text', u''), (u'Byo time', 'text', u''), (u'Stones', 'text', u'')]
            self.playsettings = [(u'Opponent range', 'text', u''), (u'Colour', 'text', u''),  (u'Main time', 'text', u''), (u'Byo time', 'text', u'')]
            self.playusersettings = [(u'Username', 'text', u''), (u'Colour', 'text', u''),  (u'Main time', 'text', u''), (u'Byo time', 'text', u'')]

            self.menu_apidsetting = (unicode('Access Point'), self.menu_apidsetting_do)
            self.menu_loginsetting = (unicode('Login'), self.menu_loginsetting_do)
            self.menu_closeall = (unicode('Close all'), self.menu_closeall_do)
            self.menu_close = (unicode('Close game'), self.menu_close_do)
            self.menu_observe = (unicode('Observe game'), self.menu_observe_do)
            self.menu_play = (unicode('Match'), self.menu_play_do)
            self.menu_automatch = (unicode('Automatch'), self.menu_automatch_do)
            self.menu_resign = (unicode('Resign'), self.menu_resign_do)
            self.menu_adjourn = (unicode('Adjourn'), self.menu_adjourn_do)
            self.menu_handicap = (unicode('Handicap'), self.menu_handicap_do)
            self.menu_komi = (unicode('Komi'), self.menu_komi_do)
            self.menu_playuser = (unicode('User'), self.menu_playuser_do)
            self.menu_exit = (unicode('Exit'), self.quit)
            self.menu_help = (unicode('Help'), self.menu_help_do)
            self.menu_return = (unicode('Close'), self.menu_return_do)

            self.menu_settings = (u'Settings', (self.menu_speech, self.menu_singlegame, self.menu_open, self.menu_blitz, self.menu_loginsetting, self.menu_apidsetting))
            #~ self.menu_settings = (u'Settings', (self.menu_loginsetting, self.menu_apidsetting, self.menu_singlegame, self.menu_open))
            self.menu_playall = (u'Play', (self.menu_automatch, self.menu_play, self.menu_playuser))
            self.menu_gameoptions1 = (u'Game options', (self.menu_handicap, self.menu_komi, self.menu_resign, self.menu_adjourn))
            self.menu_gameoptions2 = (u'Game options', (self.menu_komi, self.menu_resign, self.menu_adjourn))
            self.menu_gameoptions3 = (u'Game options', (self.menu_resign, self.menu_adjourn))
            self.menu_closecombo = (u'Close', (self.menu_close, self.menu_closeall))


            self.menu_blitz_do()
            self.menu_blitz_do()

            self.menu_speech_do()
            self.menu_speech_do()
            appuifw.app.menu = [self.menu_settings, self.menu_help, self.menu_exit]

            self.username = self.storage.GetValue('username')
            self.password = self.storage.GetValue('password')

            self.notification = 'Starting Application'

            self.menu_notification_busy = 0
            self.get_observed = 0
            self.get_play = 0
            self.get_automatch = 0

            self.tabspaneimg = TabsPaneImg()

            self.canvas = appuifw.Canvas()
            self.canvas_img = 0

            appuifw.app.screen = 'full'
            appuifw.app.title = unicode('PandaPy')

            self.canvas = appuifw.Canvas(redraw_callback=self.handle_redraw, resize_callback=self.handle_resize)

            self.canvas.bind(key_codes.EKeyUpArrow, lambda:self.UpArrow())
            self.canvas.bind(key_codes.EKeyDownArrow, lambda:self.DownArrow())
            self.canvas.bind(key_codes.EKeyRightArrow, lambda:self.RightArrow())
            self.canvas.bind(key_codes.EKeyLeftArrow, lambda:self.LeftArrow())
            self.canvas.bind(key_codes.EKeySelect, lambda:self.Select())
            self.canvas.bind(key_codes.EKeyHash, lambda:self.Hash())
            self.canvas.bind(key_codes.EKeyBackspace, lambda:self.Backspace())
            self.canvas.bind(key_codes.EKeyStar, lambda:self.Star())
            self.canvas.bind(key_codes.EKey0, lambda:self.Key0())
            self.canvas.bind(key_codes.EKey1, lambda:self.KeyNum(1))
            self.canvas.bind(key_codes.EKey2, lambda:self.KeyNum(2))
            self.canvas.bind(key_codes.EKey3, lambda:self.KeyNum(3))
            self.canvas.bind(key_codes.EKey4, lambda:self.KeyNum(4))
            self.canvas.bind(key_codes.EKey5, lambda:self.KeyNum(5))
            self.canvas.bind(key_codes.EKey6, lambda:self.KeyNum(6))
            self.canvas.bind(key_codes.EKey7, lambda:self.KeyNum(7))
            self.canvas.bind(key_codes.EKey8, lambda:self.KeyNum(8))
            self.canvas.bind(key_codes.EKey9, lambda:self.KeyNum(9))

            appuifw.app.body = self.canvas
            self.running = 1
            self.start_igs()

            self.autoswitch = 0
            self.gui_game = -1

            self.gui()


        except:
            print 'Application error'
            raise

    def menu_select(self):
        if self.helping:
            appuifw.app.menu = [self.menu_return]

        elif self.igs and self.igs.logged_in and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
            if self.igs.games[self.gui_game].movescrolling:
                self.menu_movescrolling = (unicode('Scrolling mode'), self.menu_movescrolling_do)
            else:
                self.menu_movescrolling = (unicode('Moving mode'), self.menu_movescrolling_do)
            if self.igs.games[self.gui_game].playing and not self.igs.games[self.gui_game].gameover and not self.igs.games[self.gui_game].adjourned and len(self.igs.games)==1:
                if self.igs.games[self.gui_game].lastprocessed_movenum == 0:
                    appuifw.app.menu = [self.menu_gameoptions1, self.menu_movescrolling, self.menu_close, self.menu_observe, self.menu_playall, self.menu_settings, self.menu_help]
                elif self.igs.games[self.gui_game].lastprocessed_movenum <5:
                    appuifw.app.menu = [self.menu_gameoptions2, self.menu_movescrolling, self.menu_close, self.menu_observe, self.menu_playall, self.menu_settings, self.menu_help]
                else:
                    appuifw.app.menu = [self.menu_gameoptions3, self.menu_movescrolling, self.menu_close, self.menu_observe, self.menu_playall, self.menu_settings, self.menu_help]
            elif self.igs.games[self.gui_game].playing  and not self.igs.games[self.gui_game].gameover and not self.igs.games[self.gui_game].adjourned and len(self.igs.games)>1:
                if self.igs.games[self.gui_game].lastprocessed_movenum==0:
                    appuifw.app.menu = [self.menu_gameoptions1, self.menu_movescrolling, self.menu_closecombo, self.menu_observe, self.menu_playall, self.menu_settings, self.menu_help]
                elif self.igs.games[self.gui_game].lastprocessed_movenum<3:
                    appuifw.app.menu = [self.menu_gameoptions2, self.menu_movescrolling, self.menu_closecombo, self.menu_observe, self.menu_playall, self.menu_settings, self.menu_help]
                else:
                    appuifw.app.menu = [self.menu_gameoptions3, self.menu_movescrolling, self.menu_closecombo, self.menu_observe, self.menu_playall, self.menu_settings, self.menu_help]
            elif len(self.igs.games)>1:
                appuifw.app.menu = [self.menu_movescrolling, self.menu_closecombo, self.menu_observe, self.menu_playall, self.menu_settings, self.menu_help]
            else:
                appuifw.app.menu = [self.menu_movescrolling, self.menu_close, self.menu_observe, self.menu_playall, self.menu_settings, self.menu_help]
        elif self.igs and self.igs.logged_in :
            appuifw.app.menu = [self.menu_observe, self.menu_playall, self.menu_settings, self.menu_help, self.menu_exit]
        else:
            appuifw.app.menu = [self.menu_settings, self.menu_help, self.menu_exit]

    def menu_return_do(self):
        self.helping = 0
        appuifw.app.screen = 'full'
        appuifw.app.body = self.canvas
        self.menu_select()

    def menu_help_do(self):
        self.helping = 1
        self.menu_select()
        appuifw.app.title = u'PandaPy\nHelp'
        appuifw.app.screen = 'normal'

        #Create an instance of Text and set it as the application's body
        t = appuifw.Text()
        appuifw.app.body = t

        #Set the color of the text
        t.color = 0
        #Set the font by name, size and flags
        t.font = (None, 12, None)
        #Set the color in which the text will be highlighted
        t.highlight_color = 0xFFFFFF

        #t.style = (appuifw.HIGHLIGHT_STANDARD | appuifw.STYLE_BOLD | appuifw.STYLE_UNDERLINE)
        #t.add(u"Help ")

        t.style = (appuifw.HIGHLIGHT_STANDARD | appuifw.STYLE_BOLD)


        t.add(u"(PandaPy v1.1.2 by F.P.S. Luus)")

        t.color = (255, 0, 0)
        t.add(u"\n\n Observation range")
        t.color = 0
        t.add(u" - E.g. 16k-10k, 14k, 5k-1k, 8k, 2k-3d, 7d-1d, 6d-9p etc.")
        t.color = (255, 0, 0)
        t.add(u"\n Opponent range")
        t.color = 0
        t.add(u" - E.g. 16k-10k o, 14k o, 5k-1k o, 8k o, 2k-3d o, 7d-1d o etc. where o means open for playing.")
        t.color = (255, 0, 0)
        t.add(u"\n Main time")
        t.color = 0
        t.add(u" - Time before Canadian byo-yomi in minutes e.g. 10, 5, 13 etc.")
        t.color = (255, 0, 0)
        t.add(u"\n Byo time")
        t.color = 0
        t.add(u" - Time to play the default of 25 stones in minutes e.g. 5, 7, 15 etc.")
        t.color = (255, 0, 0)
        t.add(u"\n Size")
        t.color = 0
        t.add(u" - Board size, only 19 supported at this time.")
        t.color = (255, 0, 0)
        t.add(u"\n Stones")
        t.color = 0
        t.add(u" - Amount of stones per byo-yomi period e.g. 10, 20, 21, 15, 25 etc.")
        t.color = (255, 0, 0)
        t.add(u"\n Colour")
        t.color = 0
        t.add(u" - The colour that you will be playing, i.e. W or B.")

        t.color = (255, 0, 0)
        t.add(u"\n\n Scrolling mode")
        t.color = 0
        t.add(u" - Move backward and forward through the moves of a game if menu states Scrolling mode.")
        t.color = (255, 0, 0)
        t.add(u"\n Moving mode")
        t.color = 0
        t.add(u" - Normal cursor moving.")

        t.color = (255, 0, 0)
        t.add(u"\n\nJoystick Up/Down/Left/Right")
        t.color = 0
        t.add(u" - Move between intersections if Moving Mode. If Scrolling Mode then Left->back one move, Right->forward one move, Up->latest move and Down->jump back.")
        t.color = (255, 0, 0)
        t.add(u"\nJoystick Select")
        t.color = 0
        t.add(u" - Place stone if playing a game/ Mark dead stone if scoring.")
        t.color = (255, 0, 0)
        t.add(u"\nC")
        t.color = 0
        t.add(u" - Undo move if playing/ Undo during scoring.")
        t.color = (255, 0, 0)
        t.add(u"\n1-9")
        t.color = 0
        t.add(u" - Jump to the starpoints on the goban.")
        t.color = (255, 0, 0)
        t.add(u"\n*")
        t.color = 0
        t.add(u" - Zoom in/ out.")
        t.color = (255, 0, 0)
        t.add(u"\n0")
        t.color = 0
        t.add(u" - Get open games selection list.")
        t.color = (255, 0, 0)
        t.add(u"\n#")
        t.color = 0
        t.add(u" - Pass when playing/ Done when scoring.")


    def menu_blitz_do(self):
        self.blitz_on = self.storage.GetValue('blitz')
        if self.blitz_on == None:
            self.blitz_on = 0
        if self.blitz_on:
            self.blitz_on = 0
            self.menu_blitz = (unicode('Watch blitz Off'), self.menu_blitz_do)
        else:
            self.blitz_on = 1
            self.menu_blitz = (unicode('Watch blitz On'), self.menu_blitz_do)
            if self.igs and self.igs.sock.connected:
                self.blitz_def = self.storage.GetValue('blitzdef')
                self.blitz_def = appuifw.query(unicode('Blitz byo-time (mins)'), 'text', unicode(self.blitz_def))
                try:
                    self.blitz_def = int(self.blitz_def)
                except:
                    self.blitz_def = 5
                self.storage.SetValue('blitzdef', str(self.blitz_def))
        self.menu_settings = (u'Settings', (self.menu_speech, self.menu_singlegame, self.menu_open, self.menu_blitz, self.menu_loginsetting, self.menu_apidsetting))
        #~ self.menu_settings = (u'Settings', (self.menu_loginsetting, self.menu_apidsetting, self.menu_singlegame, self.menu_open))
        self.storage.SetValue('blitz', (self.blitz_on))
        self.menu_select()

    def menu_speech_do(self):
        self.audio_on = self.storage.GetValue('speech')
        if self.audio_on == None:
            self.audio_on = 0
        if self.audio_on:
            self.audio_on = 0
            self.menu_speech = (unicode('Speech Off'), self.menu_speech_do)
        else:
            self.audio_on = 1
            self.menu_speech = (unicode('Speech On'), self.menu_speech_do)
        self.menu_settings = (u'Settings', (self.menu_speech, self.menu_singlegame, self.menu_open, self.menu_blitz, self.menu_loginsetting, self.menu_apidsetting))
        #~ self.menu_settings = (u'Settings', (self.menu_loginsetting, self.menu_apidsetting, self.menu_singlegame, self.menu_open))
        self.storage.SetValue('speech', (self.audio_on))
        self.menu_select()

    def menu_singlegame_do(self):
        if self.igs and self.igs.sock.connected:
            self.singlegame = self.storage.GetValue('singlegame')
            if self.singlegame == None:
                self.singlegame = 1
            if self.singlegame:
                self.singlegame = 0
                self.menu_singlegame = (unicode('Singlegame Off'), self.menu_singlegame_do)
                self.igs.sock.send('toggle singlegame true\r\n')
            else:
                self.singlegame = 1
                self.menu_singlegame = (unicode('Singlegame On'), self.menu_singlegame_do)
                self.igs.sock.send('toggle singlegame false\r\n')
            self.menu_settings = (u'Settings', (self.menu_speech, self.menu_singlegame, self.menu_open, self.menu_blitz, self.menu_loginsetting, self.menu_apidsetting))
            #~ self.menu_settings = (u'Settings', (self.menu_loginsetting, self.menu_apidsetting, self.menu_singlegame, self.menu_open))
            self.storage.SetValue('singlegame', (self.singlegame))
            self.menu_select()

    def menu_open_do(self):
        if self.igs and self.igs.sock.connected:
            self.open = self.storage.GetValue('open')
            if self.open == None:
                self.open = 1
            if self.open:
                self.open = 0
                self.menu_open = (unicode('Open Off'), self.menu_open_do)
                self.igs.sock.send('toggle open true\r\n')
            else:
                self.open = 1
                self.menu_open = (unicode('Open On'), self.menu_open_do)
                self.igs.sock.send('toggle open false\r\n')
            self.menu_settings = (u'Settings', (self.menu_speech, self.menu_singlegame, self.menu_open, self.menu_blitz, self.menu_loginsetting, self.menu_apidsetting))
            #~ self.menu_settings = (u'Settings', (self.menu_loginsetting, self.menu_apidsetting, self.menu_singlegame, self.menu_open))
            self.storage.SetValue('open', (self.open))
            self.menu_select()

    def menu_movescrolling_do(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
            if self.igs.games[self.gui_game].movescrolling:
                self.igs.games[self.gui_game].movescrolling = 0
                self.igs.games[self.gui_game].atmove = len(self.igs.games[self.gui_game].board_moves)-1
                self.menu_movescrolling = (unicode('Moving mode'), self.menu_movescrolling_do)
            else:
                self.igs.games[self.gui_game].movescrolling = 1
                self.menu_movescrolling = (unicode('Scrolling mode'), self.menu_movescrolling_do)
                self.downscrolljumps = self.storage.GetValue('downscrolljumps')
                if self.downscrolljumps == None:
                    self.downscrolljumps = int(appuifw.query(unicode('Down scroll jumps'), 'text', unicode('10')))
                    self.storage.SetValue('downscrolljumps', str(self.downscrolljumps))
                else:
                    self.downscrolljumps = int(self.downscrolljumps)
            self.menu_select()

    def menu_apidsetting_do(self):
        #print self.apid
        #self.apid = self.storage.GetValue('apid')
        #print self.apid
        appuifw.app.title = u'PandaPy\nAccess Point setting'
        appuifw.app.screen = 'normal'
        self.apid = socket.select_access_point()
        appuifw.app.screen = 'full'
        #print self.apid
        self.storage.SetValue('apid', self.apid)
        #print self.apid
        #self.apid = self.storage.GetValue('apid')
        #print self.apid

    def menu_loginsetting_do(self):
        temp_username = self.storage.GetValue('username')
        temp_password = self.storage.GetValue('password')
        if temp_username == None:
            temp_username = u'guest'
        if temp_password == None:
            temp_password = u''
        loginsettings = [(u'Username', 'text', temp_username), (u'Password', 'text', temp_password)]
        appuifw.app.title = u'PandaPy\nLogin settings'
        appuifw.app.screen = 'normal'
        f = appuifw.Form(loginsettings, appuifw.FFormEditModeOnly|appuifw.FFormDoubleSpaced)
        f.execute()
        appuifw.app.screen = 'full'
        self.storage.SetValue('username', f[0][2])
        self.storage.SetValue('password', f[1][2])

    def menu_handicap_do(self):
        temp = appuifw.query(unicode('Handicap stones'), 'text', u'2')

        if temp == None:
            self.gui()
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)) and self.igs.games[self.gui_game].playing:
            self.igs.move_input(u'handicap '+temp)
        #self.gui()

    def menu_komi_do(self):
        temp = appuifw.query(unicode('Komi amount'), 'text', u'5.5')

        if temp == None:
            self.gui()
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)) and self.igs.games[self.gui_game].playing:
            self.igs.move_input(u'komi '+temp)
        #self.gui()

    def menu_resign_do(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)) and self.igs.games[self.gui_game].playing:
            self.igs.move_input('resign')
        #self.gui()

    def menu_adjourn_do(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)) and self.igs.games[self.gui_game].playing:
            self.igs.move_input('adjourn')
        #self.gui()

    def menu_closeall_do(self):
        while len(self.igs.games):
            #print g, range(len(self.igs.games))
            if self.igs.games[0].playing:# and self.igs.games[self.gui_game].scoringover:
                self.igs.playinggames -= 1
            else:
                self.igs.removed = -1
                if not self.igs.games[0].gameover:
                    self.igs.sock.send('unobserve '+str(self.igs.games[0].game_number)+'\r\n')
                    #while self.igs.removed != self.igs.games[0].game_number:
                    #    e32.ao_sleep(0.1)
            self.igs.closedlist.append(self.igs.games[0].game_number)
            while self.igs.games_access:
                e32.ao_sleep(0.0001)
            del self.igs.games[0]
        self.gui_game = -1
        self.notification = ''
        self.redraw()
        #self.gui()

    def menu_close_do(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
            if self.igs.games[self.gui_game].playing:# and self.igs.games[self.gui_game].scoringover:
                self.igs.playinggames -= 1
            else:# and self.igs.games[self.gui_game].scoringover:
                self.igs.removed = -1
                if not self.igs.games[self.gui_game].gameover:
                    self.igs.sock.send('unobserve '+str(self.igs.games[self.gui_game].game_number)+'\r\n')
                    #while self.igs.removed != self.igs.games[self.gui_game].game_number:
                    #    e32.ao_sleep(0.1)
            self.igs.closedlist.append(self.igs.games[self.gui_game].game_number)
            while self.igs.games_access:
                e32.ao_sleep(0.0001)
            del self.igs.games[self.gui_game]
            if self.gui_game+1>len(self.igs.games):
                self.gui_game = len(self.igs.games)-1
            if len(self.igs.games) == 0:
                self.gui_game = -1
                self.notification = ''

            self.redraw()
        #self.gui()

    def menu_playuser_do(self):
        appuifw.app.title = u'PandaPy\nPlay specific user'
        appuifw.app.screen = 'normal'

        for i in range(4):
            self.playusersettings[i] = self.playusersettings[i][0], self.playusersettings[i][1], self.storage.GetValue('playusersettings'+str(i))
            if self.playusersettings[i][2] == None:
                self.playusersettings[i] = self.playusersettings[i][0], self.playusersettings[i][1], u''

        f = appuifw.Form(self.playusersettings, appuifw.FFormEditModeOnly|appuifw.FFormDoubleSpaced)
        f.execute()
        #print self.playusersettings
        for v in range(4):
            self.playusersettings[v] = copy.deepcopy(f[v])
        #print self.playusersettings

        for i in range(4):
            self.storage.SetValue('playusersettings'+str(i), self.playusersettings[i][2])

        appuifw.app.screen = 'full'
        self.igs.request_game(self.playusersettings[0][2], (self.playusersettings[1][2], self.playusersettings[2][2], self.playusersettings[3][2]))
        #self.gui()

    def menu_automatch_do(self):
        self.get_automatch = 0
        self.menu_notification_busy = 1

        appuifw.app.title = u'PandaPy\nAutomatch'
        appuifw.app.screen = 'normal'

        for i in range(5):
            self.automatchsettings[i] = self.automatchsettings[i][0], self.automatchsettings[i][1], self.storage.GetValue('automatchsettings'+str(i))
            if self.automatchsettings[i][2] == None:
                self.automatchsettings[i] = self.automatchsettings[i][0], self.automatchsettings[i][1],u''

        f = appuifw.Form(self.automatchsettings, appuifw.FFormEditModeOnly|appuifw.FFormDoubleSpaced)

        f.execute()
        appuifw.app.screen = 'full'

        #print self.playsettings
        for v in range(5):
            self.automatchsettings[v] = copy.deepcopy(f[v])
        #print self.playsettings

        for i in range(5):
            self.storage.SetValue('automatchsettings'+str(i), self.automatchsettings[i][2])

        thread.start_new_thread(self.igs.who_command, (self.automatchsettings[0][2], 2))

    def menu_play_do(self):
        self.get_play = 0
        self.menu_notification_busy = 1

        appuifw.app.title = u'PandaPy\nPlay users'
        appuifw.app.screen = 'normal'

        for i in range(4):
            self.playsettings[i] = self.playsettings[i][0], self.playsettings[i][1], self.storage.GetValue('playsettings'+str(i))
            if self.playsettings[i][2] == None:
                self.playsettings[i] = self.playsettings[i][0], self.playsettings[i][1],u''

        f = appuifw.Form(self.playsettings, appuifw.FFormEditModeOnly|appuifw.FFormDoubleSpaced)

        f.execute()
        appuifw.app.screen = 'full'

        #print self.playsettings
        for v in range(4):
            self.playsettings[v] = copy.deepcopy(f[v])
        #print self.playsettings

        for i in range(4):
            self.storage.SetValue('playsettings'+str(i), self.playsettings[i][2])

        thread.start_new_thread(self.igs.who_command, (self.playsettings[0][2], 1))

    def menu_observe_do(self):
        self.get_observed = 0
        self.menu_notification_busy = 1
        self.observeparams = self.storage.GetValue('observeparams')

        self.observeparams = appuifw.query(unicode('Observation range'), 'text', unicode(self.observeparams))
        if self.observeparams == None:
            return
        self.storage.SetValue('observeparams', self.observeparams)

        thread.start_new_thread(self.menu_observe_do_thread, ())

    def menu_observe_do_thread(self):
        self.notification = 'Obtaining users '

        self.igs.who_command(self.observeparams)
        self.notification = 'Obtaining games'
        self.igs.get_observed_games()

    def myexitfunc(self):
        self.locked = 0
        s = appuifw.app.screen
        appuifw.app.screen = 'large'
        appuifw.app.screen = s
        self.gui()

    def quit(self):
        if appuifw.query(unicode('Exit now?'), 'query'):
            if self.igs:
                self.igs.stop()
            self.running = 0
            self.storage.Close()
            file = open(u'C:\\Python\\Log.txt','w')
            file.write(self.igs.sock.comms_buf)
            file.close()
            #sys.exit('Exiting')

    def do_topline(self):
        if not (self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)) and (self.igs.games[self.gui_game].zoom == 100.0)):
            if self.canvas.size[0] < self.canvas.size[1]:
                self.canvas_img.rectangle((0, 0, 240, 5), fill=(180, 187, 140))
                self.canvas_img.rectangle((0, 5, 240, 7), fill=(168, 176, 121))
                self.canvas_img.rectangle((0, 7, 240, 13), fill=(155, 165, 103))

                #self.canvas_img.text((2, 10), unicode(str(int((sysinfo.signal_bars()/7.0)*100.0))), fill=(255,255,255), font=(None, 10, graphics.FONT_BOLD|graphics.FONT_ANTIALIAS))
                for i in range(sysinfo.signal_bars()):
                    self.canvas_img.line(((2*(i+1), 10), (2*(i+1), 7-i)), (255, 255, 255))

                self.canvas_img.text((60, 10), unicode('PandaPy'), fill=(4, 105, 172), font=(None, 11, graphics.FONT_BOLD|graphics.FONT_ANTIALIAS))
                self.canvas_img.text((103, 10), unicode(time.strftime("%H:%M:%S", time.localtime())), fill=(51,51,0), font=(None, 10, graphics.FONT_BOLD))
                if self.igs and self.igs.sock.connected:
                    self.canvas_img.text((20, 10), unicode(str(int((self.igs.sock.sent_bytes+self.igs.sock.recv_bytes)/1024.0)) + ' kB'), fill=(0, 0, 0), font=(None, 11, graphics.FONT_ANTIALIAS))
                    if self.igs.logged_in:
                        self.canvas_img.text((150, 10), unicode(self.username), fill=(255, 0 ,0), font=(None, 10, graphics.FONT_BOLD|graphics.FONT_ANTIALIAS))
                #self.canvas_img.text((220, 10), unicode(str(sysinfo.battery())), fill=(255,255,255), font=(None, 10, graphics.FONT_BOLD))
                self.canvas_img.line(((221, 2), (237, 2)), (255, 255, 255))
                self.canvas_img.line(((221, 10), (238, 10)), (255, 255, 255))
                self.canvas_img.line(((221, 2), (221, 10)), (255, 255, 255))
                self.canvas_img.line(((237, 2), (237, 10)), (255, 255, 255))

                for i in range(int(sysinfo.battery()/100.0*7.0)):
                    self.canvas_img.line(((235 - 2*i, 8), (235 - 2*i, 3)), (255, 255, 255))
            else:
                self.canvas_img.rectangle((0, 0, 87, 12), fill=(180, 187, 140))
                self.canvas_img.rectangle((0, 12, 87, 14), fill=(168, 176, 121))
                self.canvas_img.rectangle((0, 14, 87, 26), fill=(155, 165, 103))
                self.canvas_img.rectangle((0, 26, 87, 28), fill=(168, 176, 121))
                self.canvas_img.rectangle((0, 28, 87, 40), fill=(180, 187, 140))

                for i in range(sysinfo.signal_bars()):
                    self.canvas_img.line(((2*(i+1), 10), (2*(i+1), 7-i)), (255, 255, 255))
                if self.igs and self.igs.sock.connected:
                    self.canvas_img.text((20, 10), unicode(str(int((self.igs.sock.sent_bytes+self.igs.sock.recv_bytes)/1024.0)) + ' kB'), fill=(0, 0, 0), font=(None, 11, graphics.FONT_ANTIALIAS))
                self.canvas_img.line(((69, 2), (85, 2)), (255, 255, 255))
                self.canvas_img.line(((69, 10), (86, 10)), (255, 255, 255))
                self.canvas_img.line(((69, 2), (69, 10)), (255, 255, 255))
                self.canvas_img.line(((85, 2), (85, 10)), (255, 255, 255))
                for i in range(int(sysinfo.battery()/100.0*7.0)):
                    self.canvas_img.line(((83 - 2*i, 8), (83 - 2*i, 3)), (255, 255, 255))

                self.canvas_img.text((45, 24), unicode(time.strftime("%H:%M:%S", time.localtime())), fill=(51,51,0), font=(None, 10, graphics.FONT_BOLD))

                self.canvas_img.text((1, 24), unicode('PandaPy'), fill=(4, 105, 172), font=(None, 11, graphics.FONT_BOLD|graphics.FONT_ANTIALIAS))
                if self.igs and self.igs.sock.connected and self.igs.logged_in:
                    self.canvas_img.text((1, 38), unicode(self.username), fill=(255, 0 ,0), font=(None, 10, graphics.FONT_BOLD|graphics.FONT_ANTIALIAS))

    def do_notification(self):
        if not (self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)) and (self.igs.games[self.gui_game].zoom == 100.0)):
            if self.canvas.size[0] < self.canvas.size[1]:
                self.canvas_img.rectangle((0, 303, 240, 310), fill=(180, 187, 140))
                self.canvas_img.rectangle((0, 310, 240, 312), fill=(168, 176, 121))
                self.canvas_img.rectangle((0, 312, 240, 319), fill=(155, 165, 103))
                if not self.menu_notification_busy and self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
                    self.notification = self.igs.games[self.gui_game].status
                self.canvas_img.text((1, 315), unicode(self.notification), fill=(0,0,0), font=(None, 14, graphics.FONT_BOLD))
            else:
                self.canvas_img.rectangle((0, 229, 320, 233), fill=(180, 187, 140))
                self.canvas_img.rectangle((0, 233, 320, 335), fill=(168, 176, 121))
                self.canvas_img.rectangle((0, 235, 320, 239), fill=(155, 165, 103))
                if not self.menu_notification_busy and self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
                    self.notification = self.igs.games[self.gui_game].status
                self.canvas_img.text((1, 238), unicode(self.notification), fill=(0,0,0), font=(None, 10, graphics.FONT_BOLD))

    def do_gametabs(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)) and not (self.igs.games[self.gui_game].zoom == 100.0):
            game_tabs = []
            i = 0
            for g in self.igs.games:
                game_tabs.append(g.tabstatus)
                if self.gui_game == i:
                    game_tabs[-1] = 'current'
                i += 1
            if self.canvas.size[0] < self.canvas.size[1]:
                self.canvas_img.blit(self.tabspaneimg.get(game_tabs), target=(0,289))
            else:
                self.canvas_img.blit(self.tabspaneimg.get(game_tabs), target=(0,215))

    def do_gameboard(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
            if self.canvas.size[0] < self.canvas.size[1]:
                #if len(self.igs.games[self.gui_game].moves)>0 and (len(self.igs.games[self.gui_game].moves) == self.igs.games[self.gui_game].lastprocessed_movenum):
                #if len(self.igs.games[self.gui_game].moves)>0:
                if self.igs.games[self.gui_game].zoom == 100.0:
                    self.canvas_img.blit(self.igs.games[self.gui_game].getboard_image(240, 0), target=(4, 4))
                else:
                    self.canvas_img.blit(self.igs.games[self.gui_game].getboard_image(240, 0), target=(4, 53))
            else:
                if self.igs.games[self.gui_game].zoom == 100.0:
                    self.canvas_img.blit(self.igs.games[self.gui_game].getboard_image(240, 1), target=(4, 4))
                else:
                    self.canvas_img.blit(self.igs.games[self.gui_game].getboard_image(240, 1), target=(89, -1))
        else:
            if self.canvas.size[0] < self.canvas.size[1]:
                self.canvas_img.text((23, 170), unicode('PandaPy'), fill=(31,31,0), font=(None, 50, graphics.FONT_BOLD|graphics.FONT_ANTIALIAS))
            else:
                self.canvas_img.rectangle((0, 0, 87, 240), fill=(31,31,0))
                self.canvas_img.text((110, 124), unicode('PandaPy'), fill=(31,31,0), font=(None, 50, graphics.FONT_BOLD|graphics.FONT_ANTIALIAS))

    def do_gamedefpane(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)) and not (self.igs.games[self.gui_game].zoom == 100.0):
            if self.canvas.size[0] < self.canvas.size[1]:
                self.canvas_img.blit(self.igs.games[self.gui_game].getgamedefpane(), target=(95,289))
            else:
                self.canvas_img.blit(self.igs.games[self.gui_game].getgamedefpane(), target=(0,201))

    def do_gamescrollpane(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)) and not (self.igs.games[self.gui_game].zoom == 100.0) and self.igs.games[self.gui_game].movescrolling:
            if self.canvas.size[0] < self.canvas.size[1]:
                self.canvas_img.blit(self.igs.games[self.gui_game].getgamescrollpane(), target=(185,289))
            else:
                self.canvas_img.blit(self.igs.games[self.gui_game].getgamescrollpane(), target=(0,186))

    def do_namepane(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)) and not (self.igs.games[self.gui_game].zoom == 100.0):
            if self.canvas.size[0] < self.canvas.size[1]:
                self.canvas_img.blit(self.igs.games[self.gui_game].getnamepane(), target=(0,16))
            else:
                self.canvas_img.blit(self.igs.games[self.gui_game].getnamepanelandscape(), target=(0,42))

    def handle_resize(self, rect):
        try:
            if not self.canvas_img or not (self.canvas_img.size == self.canvas.size):
                self.canvas_img = graphics.Image.new(self.canvas.size)
                self.canvas_img.clear(0)
            self.canvas.blit(self.canvas_img)
        except:
            pass

    def handle_redraw(self, rect):
        try:
            if not self.canvas_img or not (self.canvas_img.size == self.canvas.size):
                self.canvas_img = graphics.Image.new(self.canvas.size)
                self.canvas_img.clear(0)
            self.canvas.blit(self.canvas_img)
        except:
            pass

    def retouch(self):
        self.do_gametabs()
        self.do_gamedefpane()
        self.do_gamescrollpane()
        self.do_gameboard()
        self.do_topline()
        self.do_notification()
        self.do_namepane()
        self.handle_redraw(0)

    def redraw(self):
        self.canvas_img.clear(0)
        self.retouch()

    def redraw2(self):
        self.do_topline()
        self.do_gameboard()
        self.do_namepane()
        self.handle_redraw(0)

    def UpArrow(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
            if not self.igs.games[self.gui_game].movescrolling:
                self.igs.games[self.gui_game].cursor_up()
            else:
                self.igs.games[self.gui_game].atmove = len(self.igs.games[self.gui_game].board_moves)-1

    def DownArrow(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
            if not self.igs.games[self.gui_game].movescrolling:
                self.igs.games[self.gui_game].cursor_down()
            else:
                self.igs.games[self.gui_game].atmove -=self.downscrolljumps

    def RightArrow(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
            if not self.igs.games[self.gui_game].movescrolling:
                self.igs.games[self.gui_game].cursor_right()
            else:
                self.igs.games[self.gui_game].atmove +=1

    def LeftArrow(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
            if not self.igs.games[self.gui_game].movescrolling:
                self.igs.games[self.gui_game].cursor_left()
            else:
                self.igs.games[self.gui_game].atmove -=1

    def Select(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
            if not self.igs.moving and not self.igs.games[self.gui_game].movescrolling:
                self.igs.move_input()

    def Hash(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
            if not self.igs.moving:
                if self.igs.games[self.gui_game].scoring:
                    self.igs.move_input('done')
                else:
                    self.igs.move_input('pass')

    def Backspace(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
            if not self.igs.moving:
                self.igs.move_input('undoplease')

    def Star(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
            self.igs.games[self.gui_game].change_zoom()
            #self.redraw()

    def Key0(self):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
            temp_list = []
            i = 0
            for g in self.igs.games:
                i += 1
                temp_list.append(unicode(str(i) + ' '+g.oneline()))

            appuifw.app.title = unicode('PandaPy\nChoose match')
            appuifw.app.screen = 'normal'
            temp = appuifw.selection_list(temp_list)
            if not temp == None:
                self.gui_game = temp
            #self.handle_redraw(0)
            appuifw.app.screen = 'full'

    def KeyNum(self, num):
        if self.igs and len(self.igs.games) and (self.gui_game>-1 and self.gui_game<len(self.igs.games)):
            if num == 1:
                if (self.canvas.size[0] < self.canvas.size[1] and sysinfo.display_pixels()[0]<sysinfo.display_pixels()[1]) or (self.canvas.size[0] > self.canvas.size[1] and sysinfo.display_pixels()[0]>sysinfo.display_pixels()[1]):
                    self.igs.games[self.gui_game].cursor = (3, 3)
                else:
                    self.igs.games[self.gui_game].cursor = (3, 15)
            elif num == 2:
                if (self.canvas.size[0] < self.canvas.size[1] and sysinfo.display_pixels()[0]<sysinfo.display_pixels()[1]) or (self.canvas.size[0] > self.canvas.size[1] and sysinfo.display_pixels()[0]>sysinfo.display_pixels()[1]):
                    self.igs.games[self.gui_game].cursor = (9, 3)
                else:
                    self.igs.games[self.gui_game].cursor = (3, 9)
            elif num == 3:
                if (self.canvas.size[0] < self.canvas.size[1] and sysinfo.display_pixels()[0]<sysinfo.display_pixels()[1]) or (self.canvas.size[0] > self.canvas.size[1] and sysinfo.display_pixels()[0]>sysinfo.display_pixels()[1]):
                    self.igs.games[self.gui_game].cursor = (15, 3)
                else:
                    self.igs.games[self.gui_game].cursor = (3, 3)
            elif num == 4:
                if (self.canvas.size[0] < self.canvas.size[1] and sysinfo.display_pixels()[0]<sysinfo.display_pixels()[1]) or (self.canvas.size[0] > self.canvas.size[1] and sysinfo.display_pixels()[0]>sysinfo.display_pixels()[1]):
                    self.igs.games[self.gui_game].cursor = (3, 9)
                else:
                    self.igs.games[self.gui_game].cursor = (9, 15)
            elif num == 5:
                self.igs.games[self.gui_game].cursor = (9, 9)
            elif num == 6:
                if (self.canvas.size[0] < self.canvas.size[1] and sysinfo.display_pixels()[0]<sysinfo.display_pixels()[1]) or (self.canvas.size[0] > self.canvas.size[1] and sysinfo.display_pixels()[0]>sysinfo.display_pixels()[1]):
                    self.igs.games[self.gui_game].cursor = (15, 9)
                else:
                    self.igs.games[self.gui_game].cursor = (9, 3)
            elif num == 7:
                if (self.canvas.size[0] < self.canvas.size[1] and sysinfo.display_pixels()[0]<sysinfo.display_pixels()[1]) or (self.canvas.size[0] > self.canvas.size[1] and sysinfo.display_pixels()[0]>sysinfo.display_pixels()[1]):
                    self.igs.games[self.gui_game].cursor = (3, 15)
                else:
                    self.igs.games[self.gui_game].cursor = (15, 15)
            elif num == 8:
                if (self.canvas.size[0] < self.canvas.size[1] and sysinfo.display_pixels()[0]<sysinfo.display_pixels()[1]) or (self.canvas.size[0] > self.canvas.size[1] and sysinfo.display_pixels()[0]>sysinfo.display_pixels()[1]):
                    self.igs.games[self.gui_game].cursor = (9, 15)
                else:
                    self.igs.games[self.gui_game].cursor = (15, 9)
            elif num == 9:
                if (self.canvas.size[0] < self.canvas.size[1] and sysinfo.display_pixels()[0]<sysinfo.display_pixels()[1]) or (self.canvas.size[0] > self.canvas.size[1] and sysinfo.display_pixels()[0]>sysinfo.display_pixels()[1]):
                    self.igs.games[self.gui_game].cursor = (15, 15)
                else:
                    self.igs.games[self.gui_game].cursor = (15, 3)
            self.igs.games[self.gui_game].board_img.view_center = self.igs.games[self.gui_game].cursor
            #~ if (len(self.igs.games)>num):
                #~ self.gui_game = num

    def start_igs(self):
        try:
            if self.username == None or self.password == None:
                self.menu_loginsetting_do()
                self.username = self.storage.GetValue('username')
                self.password = self.storage.GetValue('password')
            self.notification = 'Opening internet connection'
            self.igs = IGS(self, self.username, self.password, self.apid)
            while not self.igs.sock.connected and self.running:
                self.redraw()
                e32.ao_sleep(0.1)
            if not self.running:
                return

            #self.notification = 'Connecting to IGS'
            while self.igs.requests==0 and self.running:
                self.redraw()
                e32.ao_sleep(0.1)
            if not self.running:
                return

            #self.notification = 'Logging into IGS as '+ self.username
            while self.igs.requests>0 and self.running:
                self.redraw()
                e32.ao_sleep(0.1)
            if not self.running:
                return

            #self.notification = 'Logged in as '+ self.username
            self.redraw()
            self.menu_singlegame_do()
            self.menu_singlegame_do()
            self.menu_open_do()
            self.menu_open_do()
            if len(self.igs.stored) > 0:
                appuifw.app.screen = 'normal'
                appuifw.app.title = unicode('PandaPy\nLoad previous game')

                temp_select = appuifw.multi_selection_list(self.igs.stored)
                appuifw.app.screen = 'full'
                #self.canvas.clear(0)
                for t in temp_select:
                    self.igs.load_game(self.igs.stored[t])
            self.notification = ''
        except:
            raise

    def gui(self):
        i = 0
        self.redraw()
        while self.running:

            self.redraw()

            #~ i += 1
            #~ if i == 50:
                #~ i=0
            #~ if i == 0:
                #~ graphics.screenshot().save(unicode('c:\\Python\\screenshots\\'+time.strftime("%H%M%S", time.localtime())+'.png'), quality=100, compression = 'no')
            self.menu_select()
            self.check_speech()
            self.check_undo()
            self.check_offer()
            self.check_komi()
            self.check_observedgames()
            self.check_automatchgames()
            self.check_playgames()

            if(not self.igs.sock.connected):
                self.notification = "Disconnected"
            e32.ao_sleep(0.02)

    def check_speech(self):
        if self.audio_on and len(self.audiosay):
            audio.say(unicode(self.audiosay))
            self.audiosay = u''
    def check_undo(self):
        if self.get_undo:
            if appuifw.query(unicode('Allow undo?'), 'query'):
                self.allow_undo = 1
            else:
                self.allow_undo = 0
            self.get_undo = 0

    def check_offer(self):
        if self.get_offer:
            if appuifw.query(unicode(self.get_offer_content[0]), 'query'):
                self.igs.sock.send(self.get_offer_content[1])
            else:
                if len(self.get_offer_content[2]):
                    self.igs.sock.send(self.get_offer_content[2])
            self.get_offer = 0

    def check_komi(self):
        if self.get_komi:
            if appuifw.query(unicode(self.get_komi), 'query'):
                self.allow_komi = 1
            else:
                self.allow_komi = 0
            self.get_komi = 0

    def check_automatchgames(self):
        if self.get_automatch and self.igs and len(self.igs.playerinfo):
            self.igs.sock.send('defs size '+self.automatchsettings[1][2]+'\r\n')
            self.igs.sock.send('defs time '+self.automatchsettings[2][2]+'\r\n')
            self.igs.sock.send('defs byotime '+self.automatchsettings[3][2]+'\r\n')
            self.igs.sock.send('defs stones '+self.automatchsettings[4][2]+'\r\n')
            for p in self.igs.playerinfo:
                if not p.name == self.username:
                    self.igs.sock.send('automatch '+p.name+'\r\n')
            self.get_automatch = 0
            self.menu_notification_busy = 0

    def check_playgames(self):
        if self.get_play and self.igs and len(self.igs.playerinfo):
            temp_str = []
            for p in self.igs.playerinfo:
                temp_str.append(unicode(p.name+' ['+ p.strength+'] '+p.idle))

            appuifw.app.title = unicode('PandaPy\nChoose opponents')
            appuifw.app.screen = 'normal'
            temp_select = appuifw.multi_selection_list(temp_str)
            appuifw.app.screen = 'full'

            for t in temp_select:
                self.igs.request_game(self.igs.playerinfo[t].name, (self.playsettings[1][2], self.playsettings[2][2], self.playsettings[3][2]))

            self.get_play = 0
            self.menu_notification_busy = 0

    def check_observedgames(self):
        if self.get_observed and self.igs and len(self.igs.gameinfo):
            temp_str = []
            temp_index = []
            i = 0
            for g in self.igs.gameinfo:
                if not self.blitz_on or g.BY < self.blitz_def:
                    temp_str.append(unicode(g.oneline()))
                    temp_index.append(i)
                i += 1
            if len(temp_str):
                appuifw.app.title = unicode('PandaPy\nChoose matches')
                appuifw.app.screen = 'normal'
                temp_select = appuifw.multi_selection_list(temp_str)
                appuifw.app.screen = 'full'

                for t in temp_select:
                    self.igs.start_observe(temp_index[t])
            else:
                self.notification = 'Turn off or change Watch blitz'
            self.get_observed = 0
            self.menu_notification_busy = 0
try:

    application = Application()
except:
    raise

