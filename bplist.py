#coding=utf-8

import struct
from datetime import datetime, timedelta

class BPList(object):
    def __init__(self, data):
        self.data = data
        self.objects = []
        self.doc = {}
        
    def __parse_int(self, length, d):
        if length == 1:
            fmt = "!B"
        elif length == 2:
            fmt = "!H"
        elif length == 4:
            fmt = "!I"
        elif length == 8:
            fmt = "!Q"
        else:
            raise ValueError("unable to unpack %d bytes length int" % length)
        return struct.unpack(fmt, d)[0]
        
    def __bytes2str(self, b):
        """
            Compatible with bytes between py2 and py3
        """
        if isinstance(b, bytes):
            if sys.version_info.major == 3:
                return str(b, encoding="utf-8")
            elif sys.version_info.major <= 2:
                return b
        return b

        
    def __parse_float(self, length, d):
        if length == 4:
            fmt = "!f"
        elif length == 8:
            fmt = "!d"
        else:
            raise ValueError("unable to unpack %d bytes length float" % length)
        return struct.unpack(fmt, d)[0]
        
    def __parse_offset_table(self, table_data):
        self.offset_table = []
        for x in range(self.number_of_object):
            offset = self.__parse_int(self.offset_len, table_data[:self.offset_len])
            self.offset_table.append(offset)
            table_data = table_data[self.offset_len:]
            
        
    def __parse_header_info(self, header_info, d):
        if header_info == 0xF:
            info = self.__parse_int(1, d[1:2]) & 0xF
            sz = 2 ** info
            return sz+2, self.__parse_int(sz, d[2:sz+2])
        else:
            return 1, header_info
             
        
    def __parse_obj(self, d):
        header = struct.unpack("!B", d[:1])[0]
        header_type = header & 0xF0
        header_info = header & 0x0F
        if header_type == 0x00:
            if header_info == 0x0:
                return None
            elif header_info == 0x8:
                return False
            elif header_info == 0x9:
                return True
            else:
                raise ValueError("unable unpack this object %x" % header)
        elif header_type == 0x10:
            return self.__parse_int(2**header_info, d[1:2**header_info+1])
        elif header_type == 0x20:
            return self.__parse_float(2**header_info, d[1:2**header_info+1])
        elif header_type == 0x30:
            td = self.__parse_int(8, d[1:9])
            return datetime(year=2001,month=1,day=1) + timedelta(seconds=td)
        elif header_type == 0x40:
            if header_info == 0xF:
                length = self.__parse_int(1, d[1:2])
                return d[2:length + 2]
            else:
                return d[1:header_info+1]
        elif header_type == 0x50:
            offset, length = self.__parse_header_info(header_info, d)
            return d[offset:length+offset].decode("ascii")
        elif header_type == 0x60:
            offset, length = self.__parse_header_info(header_info, d)
            return d[offset:length*2+offset].decode("utf-16be")
        elif header_type == 0x80:
            offset, length = self.__parse_header_info(header_info, d)
            return d[offset:length+offset].decode("ascii")
        elif header_type == 0xA0:
            arr = []
            offset, length = self.__parse_header_info(header_info, d)
            d = d[offset:]
            for x in range(length):
                ele = self.__parse_int(self.object_ref_len, d[:self.object_ref_len])
                d = d[self.object_ref_len:]
                arr.append(ele)
            return arr
        elif header_type == 0xC0:
            arr = []
            offset, length = self.__parse_header_info(header_info, d)
            d = d[offset:]
            for x in range(length):
                ele = self.__parse_int(self.object_ref_len, d[:self.object_ref_len])
                d = d[self.object_ref_len:]
                arr.append(ele)
            return arr
        elif header_type == 0xD0:
            dct = {}
            offset, length = self.__parse_header_info(header_info, d)
            d = d[offset:]
            keys = []
            for x in range(length):
                ele = self.__parse_int(self.object_ref_len, d[:self.object_ref_len])
                d = d[self.object_ref_len:]
                keys.append(ele)
            values = []
            for x in range(length):
                ele = self.__parse_int(self.object_ref_len, d[:self.object_ref_len])
                d = d[self.object_ref_len:]
                values.append(ele)
            for x, y in zip(keys, values):
                dct[x] = y
            return dct
        
    def __parse_objects(self):
        self.objects = []
        for offset in self.offset_table:
            obj = self.__parse_obj(self.data[offset:])
            self.objects.append(obj)
            
    def __parse_doc(self, idx):
        try:
            return self.doc[idx]
        except KeyError:
            obj = self.__bytes2str(self.objects[idx])
            if type(obj) == list:
                newArr = []
                for i in obj:
                    newArr.append(self.__parse_doc(i))
                self.doc[idx] = newArr
                return newArr
            if type(obj) == dict:
                newDic = {}
                for k,v in obj.items():
                    rk = self.__parse_doc(k)
                    rv = self.__parse_doc(v)
                    newDic[rk] = rv
                self.doc[idx] = newDic
                return newDic
            else:
                self.doc[idx] = obj
                return obj
        
    def parse(self):
        """
            read more about the file format:
            "http://blog.afantree.com/ios/binary-plist-format-introduce.html"
        
        """
        # judge the file magic
        assert self.data[:8] == b"bplist00", "not bplist magic header"
        
        # parse the file tail
        tail = self.data[-32:]
        self.offset_len, self.object_ref_len, self.number_of_object, \
        self.root_object, self.table_offset  = struct.unpack("!6xBB4xI4xI4xI", tail)
        self.__parse_offset_table(self.data[self.table_offset:-32])
        self.__parse_objects()
        return self.__parse_doc(self.root_object)
    
    @classmethod
    def plistWithString(cls, data):
        """
            parse the data and return the plist info
        """
        parser = cls(data)
        return parser.parse()
        
    @classmethod
    def plistWithFile(cls, filename):
        """
            parse the file and return the plist info
        """
        with open(filename, 'rb') as f:
            s = f.read()
        return cls.plistWithString(s)
            
        