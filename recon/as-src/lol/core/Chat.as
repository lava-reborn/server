class lol.core.Chat
{
   var XMC;
   var channelList;
   var dispatchEvent;
   var msgBuffer;
   var playerName_arr;
   var sendFromID;
   var sendGroup;
   var sendMess;
   var sendMessUnescape;
   var sendWithName;
   static var CHAT_LOCATION_CHANNEL = 0;
   static var CHAT_PARTY_CHANNEL = 1;
   static var CHAT_CLAN_CHANNEL = 2;
   static var CHAT_EVENT_CHANNEL = 3;
   static var CHAT_TRADE_CHANNEL = 4;
   static var CHAT_HELP_CHANNEL = 5;
   static var CHAT_WORLD_CHANNEL = 6;
   static var CHAT_PRIVATE_CHANNEL = -1;
   function Chat()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("userMsg",this);
      this.channelList = new Array();
      this.playerName_arr = new Array();
      this.msgBuffer = new Array();
   }
   function systemMessage(group, fromID, mess)
   {
      var _loc2_ = new Object();
      _loc2_.param = {group:group,from:fromID,entry:mess};
      this.userMsg(_loc2_);
   }
   function findTerminators(str)
   {
      var _loc6_ = false;
      var _loc4_ = str.indexOf("^",0);
      var _loc3_;
      var _loc5_;
      if(_loc4_ == 0)
      {
         _loc3_ = str.indexOf("^",_loc4_ + 1);
         if(str.charAt(_loc3_ - 1) == "L")
         {
            _loc5_ = str.substring(_loc4_ + 1,_loc3_ - 1);
            _loc6_ = true;
         }
         else
         {
            _loc5_ = str.substring(_loc4_ + 1,_loc3_);
         }
      }
      var _loc7_ = str.substring(_loc3_ + 1);
      var _loc1_ = new Object();
      if(_loc5_.length > 0)
      {
         _loc1_.index = Number(_loc5_);
      }
      else
      {
         _loc1_.index = undefined;
      }
      _loc1_.str = _loc7_;
      _loc1_.last_str = _loc6_;
      return _loc1_;
   }
   function userMsg(obj)
   {
      var _loc4_ = obj.param.group;
      var _loc6_ = obj.param.from;
      var _loc10_ = lol.server.XMLString.unescape(obj.param.entry);
      var _loc14_ = obj.param.nick;
      if(_loc4_ == undefined && _loc6_ != undefined)
      {
         _loc4_ = lol.core.Chat.CHAT_PRIVATE_CHANNEL;
      }
      if(_loc4_ == lol.core.Chat.CHAT_CLAN_CHANNEL)
      {
         _loc6_ = obj.param.player;
      }
      var _loc11_ = true;
      var _loc2_ = this.findTerminators(_loc10_);
      var _loc3_;
      var _loc12_;
      var _loc7_;
      var _loc8_;
      var _loc5_;
      var _loc9_;
      var _loc13_;
      if(_loc2_.index != undefined)
      {
         if(_loc2_.last_str == true)
         {
            _loc3_ = 0;
            while(_loc3_ < this.msgBuffer.length)
            {
               if(this.msgBuffer[_loc3_].group == _loc4_ && this.msgBuffer[_loc3_].fromID == _loc6_)
               {
                  _loc10_ = this.msgBuffer[_loc3_].str + _loc2_.str;
                  this.msgBuffer.splice(_loc3_,1);
                  _loc11_ = true;
                  break;
               }
               _loc3_ = _loc3_ + 1;
            }
         }
         else
         {
            _loc12_ = true;
            _loc3_ = 0;
            while(_loc3_ < this.msgBuffer.length)
            {
               if(this.msgBuffer[_loc3_].group == _loc4_ && this.msgBuffer[_loc3_].fromID == _loc6_)
               {
                  _loc7_ = "private ";
                  _loc5_ = _loc2_.str.indexOf(_loc7_,0);
                  if(_loc5_ >= 0)
                  {
                     _loc9_ = _loc2_.str.indexOf(":",_loc5_);
                     _loc8_ = _loc2_.str.substring(_loc9_ + 1,_loc2_.str.length);
                     _loc2_.str = _loc8_;
                  }
                  this.msgBuffer[_loc3_].str += _loc2_.str;
                  _loc12_ = false;
                  break;
               }
               _loc3_ = _loc3_ + 1;
            }
            if(_loc12_)
            {
               _loc13_ = new Object();
               _loc13_.group = _loc4_;
               _loc13_.fromID = _loc6_;
               _loc13_.str = _loc2_.str;
               if(_loc14_ != undefined)
               {
                  _loc13_.fromName = _loc14_;
               }
               this.msgBuffer.push(_loc13_);
            }
            _loc11_ = false;
         }
      }
      var _loc16_;
      if(_loc11_)
      {
         _loc16_ = this.isChat(_loc4_,_loc6_);
         if(_loc16_ != undefined)
         {
            this.refreshChannel(_loc6_,_loc10_,_loc16_,_loc4_,undefined,_loc14_);
         }
         else if(_loc4_ == lol.core.Chat.CHAT_HELP_CHANNEL && lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_HELP_CHANNEL) || _loc4_ == lol.core.Chat.CHAT_WORLD_CHANNEL && lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_WORLD_CHANNEL) || _loc4_ == lol.core.Chat.CHAT_TRADE_CHANNEL && lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_TRADE_CHANNEL) || _loc4_ == lol.core.Chat.CHAT_EVENT_CHANNEL && lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_EVENT_CHANNEL) || _loc4_ == lol.core.Chat.CHAT_PRIVATE_CHANNEL || _loc4_ == lol.core.Chat.CHAT_LOCATION_CHANNEL || _loc4_ == lol.core.Chat.CHAT_CLAN_CHANNEL || _loc4_ == lol.core.Chat.CHAT_PARTY_CHANNEL)
         {
            this.createNewChannel(_loc4_,_loc6_,undefined,_loc10_,_loc14_);
         }
      }
   }
   function getName(fromID)
   {
      var _loc1_;
      var _loc2_ = lol.core.Master.getInstance();
      var _loc3_ = _loc2_.getPlayer(fromID);
      _loc1_ = _loc3_.playerInfo.name;
      if(_loc1_)
      {
         return _loc1_;
      }
      return "***";
   }
   function getClanName(fromID)
   {
      var _loc2_;
      var _loc1_ = lol.core.clans.ClanInspector.getInstance().getClanMemberList();
      if(fromID == lol.core.player.Gamer.ID)
      {
         return lol.core.Master.getInstance().gamer.playerInfo.name;
      }
      for(var _loc4_ in _loc1_)
      {
         if(fromID == _loc1_[_loc4_].char)
         {
            _loc2_ = _loc1_[_loc4_].name;
            return _loc2_;
         }
      }
   }
   function isChat(isChat_group, isChat_id)
   {
      var _loc2_;
      for(var _loc5_ in this.channelList)
      {
         if(this.channelList[_loc5_].group == lol.core.Chat.CHAT_PRIVATE_CHANNEL && isChat_group == undefined && isChat_id != undefined)
         {
            return _loc5_;
         }
         if(this.channelList[_loc5_].group == isChat_group)
         {
            if(this.channelList[_loc5_].group != undefined)
            {
               _loc2_ = _loc5_;
               break;
            }
            if(this.channelList[_loc5_].withID == isChat_id)
            {
               _loc2_ = _loc5_;
               break;
            }
         }
      }
      return _loc2_;
   }
   function sendMessage(obj)
   {
      this.sendGroup = obj.group;
      this.sendWithName = obj.to;
      this.sendMess = obj.mess;
      this.sendMessUnescape = obj.mess;
      var _loc4_;
      var _loc2_;
      if(this.sendGroup != undefined)
      {
         if(this.sendWithName != undefined)
         {
            _loc2_ = new lol.server.mess.CSM_ChatMessage(new lol.data.GDString(this.sendWithName),this.sendGroup,new lol.data.GDString(this.sendMess));
         }
         else
         {
            _loc2_ = new lol.server.mess.CSM_ChatMessage(undefined,this.sendGroup,new lol.data.GDString(this.sendMess));
         }
      }
      else
      {
         _loc2_ = new lol.server.mess.CSM_ChatMessage(new lol.data.GDString(this.sendWithName),undefined,new lol.data.GDString(this.sendMess));
      }
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.delivery);
      }
   }
   function delivery(obj)
   {
      var _loc2_ = obj.param.res;
      if(_loc2_ == 0)
      {
         this.sendFromID = lol.core.player.Gamer.ID;
         this.sendMess = this.sendMessUnescape;
      }
      if(_loc2_ == 9)
      {
         this.sendFromID = "server";
      }
      this.newMessage(this.sendGroup,this.sendFromID,this.sendWithName,this.sendMess);
      this.dispatchEvent({type:"deliver"});
   }
   function newMessage(new_group, new_fromID, new_withName, new_mess)
   {
      if(new_group == undefined && new_fromID != undefined)
      {
         new_group = lol.core.Chat.CHAT_PRIVATE_CHANNEL;
      }
      var _loc6_ = new_mess;
      var _loc4_ = this.findTerminators(_loc6_);
      var _loc7_ = true;
      var _loc2_;
      var _loc8_;
      var _loc9_;
      if(_loc4_.index != undefined)
      {
         if(_loc4_.last_str == true)
         {
            _loc2_ = 0;
            while(_loc2_ < this.msgBuffer.length)
            {
               if(this.msgBuffer[_loc2_].group == new_group && this.msgBuffer[_loc2_].fromID == new_fromID)
               {
                  _loc6_ = this.msgBuffer[_loc2_].str + _loc4_.str;
                  this.msgBuffer.splice(_loc2_,1);
                  _loc7_ = true;
                  break;
               }
               _loc2_ = _loc2_ + 1;
            }
         }
         else
         {
            _loc8_ = true;
            _loc2_ = 0;
            while(_loc2_ < this.msgBuffer.length)
            {
               if(this.msgBuffer[_loc2_].group == new_group && this.msgBuffer[_loc2_].fromID == new_fromID)
               {
                  this.msgBuffer[_loc2_].str += _loc4_.str;
                  _loc8_ = false;
                  break;
               }
               _loc2_ = _loc2_ + 1;
            }
            if(_loc8_)
            {
               _loc9_ = new Object();
               _loc9_.group = new_group;
               _loc9_.fromID = new_fromID;
               _loc9_.str = _loc4_.str;
               this.msgBuffer.push(_loc9_);
            }
            _loc7_ = false;
         }
      }
      var _loc10_;
      if(_loc7_)
      {
         _loc10_ = this.isChat(new_group,new_withName);
         if(_loc10_ != undefined)
         {
            this.refreshChannel(new_fromID,_loc6_,_loc10_,new_group,new_withName);
         }
         else
         {
            this.createNewChannel(new_group,new_fromID,new_withName,_loc6_);
         }
      }
   }
   function createNewChannel(create_group, create_fromID, create_withID, create_mess, createFromName)
   {
      var _loc5_;
      var _loc0_;
      if(createFromName == undefined)
      {
         if(create_fromID == "server" || create_fromID == "events" || create_fromID == "Подсказка")
         {
            _loc5_ = create_fromID;
         }
         else if((_loc0_ = create_group) !== lol.core.Chat.CHAT_CLAN_CHANNEL)
         {
            _loc5_ = this.getName(create_fromID);
         }
         else
         {
            _loc5_ = this.getClanName(create_fromID);
         }
      }
      else
      {
         _loc5_ = createFromName;
      }
      var _loc7_ = new Array();
      var _loc2_ = new Object();
      _loc2_.fromID = create_fromID;
      _loc2_.mess = create_mess;
      _loc2_.name = _loc5_;
      _loc2_.group = create_group;
      _loc2_.to_name = create_withID;
      _loc2_.time = this.getTime();
      _loc7_.push(_loc2_);
      var _loc4_ = new Object();
      if(create_group == undefined)
      {
         _loc4_.group = lol.core.Chat.CHAT_LOCATION_CHANNEL;
      }
      else
      {
         _loc4_.group = create_group;
      }
      _loc4_.name = create_withID;
      _loc4_.logArr = _loc7_;
      this.channelList.push(_loc4_);
      this.dispatchChannel(this.channelList[this.channelList.length - 1]);
   }
   function refreshChannel(refresh_fromeID, refresh_mess, refresh_num, refresh_group, refresh_WithID, refreshFromName)
   {
      var _loc4_;
      if(refreshFromName == undefined)
      {
         if(refresh_fromeID == "server" || refresh_fromeID == "events")
         {
            _loc4_ = refresh_fromeID;
         }
         else
         {
            _loc4_ = refresh_group != lol.core.Chat.CHAT_CLAN_CHANNEL ? this.getName(refresh_fromeID) : this.getClanName(refresh_fromeID);
         }
      }
      else
      {
         _loc4_ = refreshFromName;
      }
      var _loc2_ = new Object();
      _loc2_.fromID = refresh_fromeID;
      _loc2_.mess = refresh_mess;
      _loc2_.name = _loc4_;
      _loc2_.group = refresh_group;
      _loc2_.to_name = refresh_WithID;
      _loc2_.time = this.getTime();
      this.channelList[refresh_num].logArr.push(_loc2_);
      this.dispatchChannel(this.channelList[refresh_num]);
   }
   function removeChannel(remove_withID, remove_group)
   {
      var _loc2_ = this.isChat(remove_group,remove_withID);
      if(_loc2_ != undefined)
      {
         this.channelList.splice(_loc2_,1);
      }
   }
   function eraseChannel(remove_withID, remove_group)
   {
      var _loc2_ = this.isChat(remove_group,remove_withID);
      var _loc3_;
      if(_loc2_ != undefined)
      {
         _loc3_ = new Array();
         delete this.channelList[_loc2_].logArr;
         this.channelList[_loc2_].logArr = _loc3_;
      }
   }
   function dispatchChannel(disObj)
   {
      disObj.type = "refresh";
      this.dispatchEvent(disObj);
   }
   function getChannel(get_group, get_withID)
   {
      var _loc2_;
      for(var _loc4_ in this.channelList)
      {
         if(this.channelList[_loc4_].group == get_group)
         {
            if(this.channelList[_loc4_].group == undefined)
            {
               _loc2_ = Number(_loc4_);
               break;
            }
            _loc2_ = Number(_loc4_);
            break;
         }
      }
      return this.channelList[_loc2_];
   }
   function getChannelList()
   {
      return this.channelList;
   }
   function updateChannel(oldID, newID)
   {
      var _loc8_ = lol.core.Master.getInstance();
      var _loc9_ = _loc8_.getPlayer(newID);
      var _loc4_ = _loc9_.playerInfo.name;
      var _loc3_;
      for(var _loc6_ in this.channelList)
      {
         if(this.channelList[_loc6_].withID == oldID)
         {
            _loc3_ = _loc6_;
            break;
         }
      }
      this.channelList[_loc3_].withID = newID;
      this.channelList[_loc3_].name = _loc4_;
      var _loc2_ = this.channelList[_loc3_].logArr;
      for(_loc6_ in _loc2_)
      {
         if(_loc2_[_loc6_].fromID != lol.core.player.Gamer.ID && _loc2_[_loc6_].fromID != "server")
         {
            _loc2_[_loc6_].fromID = newID;
            _loc2_[_loc6_].name = _loc4_;
         }
      }
   }
   function updateMainChannel(newID, newName)
   {
      var _loc4_;
      for(var _loc6_ in this.channelList)
      {
         if(this.channelList[_loc6_].group == 0)
         {
            _loc4_ = _loc6_;
            break;
         }
      }
      var _loc2_ = this.channelList[_loc4_].logArr;
      for(_loc6_ in _loc2_)
      {
         if(_loc2_[_loc6_].fromID != lol.core.player.Gamer.ID && _loc2_[_loc6_].fromID != "server" && _loc2_[_loc6_].name == newName)
         {
            _loc2_[_loc6_].fromID = newID;
            _loc2_[_loc6_].name = newName;
         }
      }
   }
   function getTime()
   {
      var _loc1_ = new Date();
      var _loc3_ = _loc1_.getHours() >= 10 ? _loc1_.getHours() : "0" + _loc1_.getHours();
      var _loc4_ = _loc1_.getMinutes() >= 10 ? _loc1_.getMinutes() : "0" + _loc1_.getMinutes();
      var _loc2_ = _loc3_ + ":" + _loc4_;
      return _loc2_;
   }
}
