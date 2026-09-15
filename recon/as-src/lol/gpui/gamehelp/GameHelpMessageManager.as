class lol.gpui.gamehelp.GameHelpMessageManager
{
   var HTTP;
   var _alpha;
   var alreadyShown;
   var content;
   var htmlText;
   var message_arr;
   var pic_id;
   var stackMessage;
   var title;
   var xmlArr;
   var xmlInfoLoaded;
   static var ghmmInstance;
   static var ghmmSingleCreation;
   static var GOLD_MESSAGE_TIMEOUT = 20000;
   var MESSAGE_WIDTH = 260;
   var SPAN = -3;
   function GameHelpMessageManager()
   {
      if(!lol.gpui.gamehelp.GameHelpMessageManager.ghmmSingleCreation)
      {
         trace("New GameHelpMessageManager error! Use getInstance method.");
      }
      else
      {
         this.init();
      }
   }
   static function getInstance()
   {
      if(!lol.gpui.gamehelp.GameHelpMessageManager.ghmmInstance)
      {
         lol.gpui.gamehelp.GameHelpMessageManager.ghmmSingleCreation = true;
         lol.gpui.gamehelp.GameHelpMessageManager.ghmmInstance = new lol.gpui.gamehelp.GameHelpMessageManager();
         lol.gpui.gamehelp.GameHelpMessageManager.ghmmSingleCreation = false;
      }
      return lol.gpui.gamehelp.GameHelpMessageManager.ghmmInstance;
   }
   function loadDescription()
   {
      this.xmlInfoLoaded = false;
      this.HTTP = new lol.server.HTTPRequest();
      this.HTTP.addEventListener("onXML",this);
      var _loc2_ = lol.services.SSEmulator.getHintsDescURL();
      this.HTTP.Send("",_loc2_);
   }
   function onXML(obj)
   {
      this.xmlInfoLoaded = true;
      this.parse(obj.data);
      this.HTTP.removeEventListener("onXML",this);
      this.HTTP.kill();
      this.HTTP = null;
   }
   function parse(doc)
   {
      this.xmlArr = new Array();
      var _loc5_ = doc.firstChild.childNodes;
      var _loc3_;
      var _loc4_;
      var _loc2_;
      for(var _loc7_ in _loc5_)
      {
         _loc3_ = new Object();
         _loc3_ = _loc5_[_loc7_].attributes;
         _loc4_ = new Array();
         _loc2_ = _loc5_[_loc7_].childNodes;
         for(var _loc6_ in _loc2_)
         {
            _loc4_.push(_loc2_[_loc6_].childNodes[0]);
         }
         _loc3_.arr = _loc4_;
         this.xmlArr["hint" + _loc5_[_loc7_].attributes.id] = _loc3_;
      }
   }
   function init()
   {
      lol.core.SceneShifter._ref.addEventListener("resizeStage",this,this.resizeStage);
      lol.core.SceneShifter._ref.setMCSize();
      this.stackMessage = new Array();
      var _loc2_ = lol.core.SceneShifter.linkWindow;
      this.content = _loc2_.createEmptyMovieClip("gamehelpMessage_mc",_loc2_.getNextHighestDepth());
      this.message_arr = new Array();
      this.alreadyShown = new Array();
   }
   function setMessageID(type_id)
   {
      for(var _loc3_ in this.xmlArr)
      {
         if(this.xmlArr[_loc3_].id == type_id)
         {
            this.title = this.xmlArr[_loc3_].title;
            this.htmlText = this.xmlArr[_loc3_].description;
            this.pic_id = this.xmlArr[_loc3_].image_res;
            break;
         }
      }
   }
   function resizeStage(obj)
   {
      if(Stage.width > 1200)
      {
         this.content._x = -40;
      }
      else
      {
         this.content._x = (1200 - Stage.width) / 2;
      }
      this.content._y = (- Stage.height) / 2 + obj.h - lol.services.ChatPan.DEFAULT_H - 50;
      if(!this.xmlInfoLoaded)
      {
         this.loadDescription();
      }
   }
   function newMessage(type_id)
   {
      if(!type_id)
      {
         return undefined;
      }
      for(var _loc3_ in this.alreadyShown)
      {
         if(_loc3_ == type_id && this.alreadyShown[_loc3_] == true)
         {
            return undefined;
         }
      }
      var _loc4_;
      var _loc2_;
      if(this.message_arr.length <= 4)
      {
         _loc4_ = this.message_arr.length;
         _loc2_ = this.content.attachMovie("GameHelpMessage","GameHelpMessage" + _loc4_,this.content.getNextHighestDepth());
         _loc2_.type_id = type_id;
         _loc2_.id = _loc4_;
         _loc2_.help_manager = this;
         var k = true;
         var count = 0;
         _loc2_.bg.onEnterFrame = function()
         {
            if(k)
            {
               if(count < 100)
               {
                  count += 10;
               }
               else
               {
                  count = 100;
                  this._alpha = 100;
                  k = false;
               }
            }
            else if(count > 0)
            {
               count -= 10;
            }
            else
            {
               count = 0;
               this._alpha = 0;
               k = true;
            }
         };
         _loc2_.addEventListener(lol.gpui.gamehelp.GameHelpMessage.REMOVE_MESSAGE,this,this.removeMessage);
         this.message_arr.push(_loc2_);
         _loc2_._x = this.getWidth() - 30;
         _loc2_._y = -40;
         this.alreadyShown[type_id] = true;
         return _loc2_;
      }
      this.stackMessage.push({type_id:type_id});
   }
   function newNPCGameHelpMessage(npc_name)
   {
      for(var _loc3_ in this.xmlArr)
      {
         if(this.xmlArr[_loc3_].npc == npc_name)
         {
            this.newMessage(this.xmlArr[_loc3_].id);
         }
      }
   }
   function newLocationGameHelpMessage(loc_name)
   {
      for(var _loc3_ in this.xmlArr)
      {
         if(this.xmlArr[_loc3_].location == loc_name)
         {
            this.newMessage(this.xmlArr[_loc3_].id);
         }
      }
   }
   function newQuestGameHelpMessage(quest_name)
   {
      for(var _loc3_ in this.xmlArr)
      {
         if(this.xmlArr[_loc3_].quest == quest_name)
         {
            this.newMessage(this.xmlArr[_loc3_].id);
         }
      }
   }
   function newQuestTypeMessage(quest_type)
   {
      for(var _loc3_ in this.xmlArr)
      {
         if(this.xmlArr[_loc3_].quest_type == String(quest_type))
         {
            this.newMessage(this.xmlArr[_loc3_].id);
         }
      }
   }
   function newInterfaceGameHelpMessage(window_name)
   {
      for(var _loc3_ in this.xmlArr)
      {
         if(this.xmlArr[_loc3_].window_name == window_name)
         {
            this.newMessage(this.xmlArr[_loc3_].id);
         }
      }
   }
   function newSkillLevelUpGameHelpMessage()
   {
      for(var _loc2_ in this.xmlArr)
      {
         if(this.xmlArr[_loc2_].rp_up == "skill")
         {
            this.newMessage(this.xmlArr[_loc2_].id);
         }
      }
   }
   function newStartGameHelpMessage()
   {
      for(var _loc2_ in this.xmlArr)
      {
         if(this.xmlArr[_loc2_].showOnStart == "true")
         {
            this.newMessage(this.xmlArr[_loc2_].id);
         }
      }
   }
   function newSpecLevelUpGameHelpMessage()
   {
      for(var _loc2_ in this.xmlArr)
      {
         if(this.xmlArr[_loc2_].rp_up == "spec")
         {
            this.newMessage(this.xmlArr[_loc2_].id);
         }
      }
   }
   function removeMessage(obj)
   {
      var _loc4_ = obj.target.id;
      var _loc6_ = Math.abs(this.message_arr[_loc4_ + 1]._width + this.message_arr[_loc4_ + 1]._x);
      this.message_arr[_loc4_].closeMessage();
      this.message_arr[_loc4_].removeEventListener(lol.gpui.gamehelp.GameHelpMessage.REMOVE_MESSAGE,this,this.removeMessage);
      this.message_arr.splice(_loc4_,1);
      var _loc2_ = _loc4_;
      var _loc3_;
      while(_loc2_ < this.message_arr.length)
      {
         _loc3_ = this.getSlideToX(_loc2_);
         this.message_arr[_loc2_].id = _loc2_;
         this.message_arr[_loc2_].slide(_loc3_);
         _loc2_ = _loc2_ + 1;
      }
      var _loc5_;
      if(this.stackMessage.length > 0)
      {
         _loc5_ = this.stackMessage.shift();
         this.newMessage(_loc5_.type_id);
      }
   }
   function getWidth()
   {
      var _loc3_ = 0;
      var _loc2_ = 0;
      while(_loc2_ < this.message_arr.length)
      {
         _loc3_ += this.message_arr[_loc2_]._width + this.SPAN;
         _loc2_ = _loc2_ + 1;
      }
      return _loc3_;
   }
   function getSlideToX(id)
   {
      var _loc3_ = this.message_arr[id]._width;
      var _loc2_ = 0;
      while(_loc2_ < this.message_arr.length)
      {
         if(_loc2_ == id)
         {
            break;
         }
         _loc3_ += this.message_arr[_loc2_]._width + this.SPAN;
         _loc2_ = _loc2_ + 1;
      }
      return _loc3_;
   }
}
