class lol.gpui.MarksAndPlayersPan extends lol.gpui.GPUIObject
{
   var BY;
   var SO;
   var TTY;
   var TY;
   var _parent;
   var _y;
   var closeEQ;
   var dispatchEvent;
   var doLater;
   var hideMarksAndPlayers_btn;
   var markInfoPan;
   var markList_mc;
   var marks_btn;
   var onEnterFrame;
   var openEQ;
   var trans_btn;
   var transport_mc;
   var userInfo_mc;
   var userList_mc;
   var users_btn;
   var panActivationFlag = false;
   function MarksAndPlayersPan()
   {
      super();
      this.SO = SharedObject.getLocal("csettings","/");
      this.panActivationFlag = !this.SO.data.marksAndPlayersPanVisible ? this.panActivationFlag : this.SO.data.marksAndPlayersPanVisible;
      if(this.panActivationFlag)
      {
         this._parent.rightMask.gotoAndStop(2);
      }
      this.propeties();
      this.doLater("init");
   }
   function propeties()
   {
      if(this.panActivationFlag)
      {
         this.TY = this._y;
      }
      else
      {
         this.TY = this._y - 122;
      }
      this.TTY = this.TY - 30;
      this.BY = this.TY + 122;
      this.openEQ = new lol.events.EventQueue();
      this.openEQ.addEvent(this,"slide",[this.TTY],0);
      this.openEQ.addEvent(this._parent.rightMask,"gotoAndStop",[2],200);
      this.openEQ.addEvent(this,"slide",[this.TY],0);
      this.closeEQ = new lol.events.EventQueue();
      this.closeEQ.addEvent(this,"slide",[this.TTY],0);
      this.closeEQ.addEvent(this._parent.rightMask,"gotoAndStop",[1],200);
      this.closeEQ.addEvent(this,"slide",[this.BY],0);
   }
   function init()
   {
      this.users_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.switchInfo);
      this.marks_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.switchInfo);
      this.trans_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.switchInfo);
      this.hideMarksAndPlayers_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.panActivation);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.MARKS_AND_PLAYERS_PAN,this,this.panActivation);
      var _loc4_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.LABEL_OR_PLAYERS);
      if(_loc4_ == "label")
      {
         this.switchInfo({target:this.marks_btn});
      }
      else if(_loc4_ == "transport")
      {
         this.switchInfo({target:this.trans_btn});
      }
      else
      {
         this.switchInfo({target:this.users_btn});
      }
      var _loc3_ = lol.core.Master.getInstance().gamer.playerInfo.transport;
      var _loc2_ = lol.core.Master.getInstance().gamer.playerInfo.transRentTime;
      if(_loc3_ && _loc2_ != undefined)
      {
         this.transport_mc.attachIconEnabled = true;
         this.transport_mc.priceEnabled = false;
         this.transport_mc.item = _loc3_;
         this.transport_mc.attachIcon(_loc3_);
         if(_loc2_ > 24)
         {
            this.transport_mc.time_txt.text = "ОСТАВШЕЕСЯ ВРЕМЯ: " + Math.floor(_loc2_ / 24) + " ДН. " + _loc2_ % 24 + " Ч.";
         }
         else
         {
            this.transport_mc.time_txt.text = "ОСТАВШЕЕСЯ ВРЕМЯ: " + _loc2_ + " Ч.";
         }
      }
      else
      {
         this.transport_mc.name_txt.text = "У ВАС НЕТ ТРАНСПОРТА";
      }
   }
   function kill()
   {
      this.users_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.switchInfo);
      this.marks_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.switchInfo);
      this.trans_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.switchInfo);
      this.openEQ.kill();
      this.closeEQ.kill();
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.MARKS_AND_PLAYERS_PAN,this,this.panActivation);
   }
   function slide(y)
   {
      this.onEnterFrame = function()
      {
         this._y += (y - this._y) / 2;
         if(Math.abs(y - this._y) < 2)
         {
            this._y = y;
            delete this.onEnterFrame;
         }
      };
   }
   function panActivation()
   {
      this.panActivationFlag = !this.panActivationFlag;
      if(this.panActivationFlag)
      {
         this.openEQ.Start();
      }
      else
      {
         this.closeEQ.Start();
      }
      this.SO.data.marksAndPlayersPanVisible = this.panActivationFlag;
      this.SO.flush();
   }
   function switchInfo(obj)
   {
      if(obj.target == this.users_btn)
      {
         this.users_btn.toggled = true;
         this.marks_btn.toggled = false;
         this.trans_btn.toggled = false;
         this.userList_mc._visible = true;
         this.markList_mc._visible = false;
         this.markInfoPan._visible = false;
         this.userInfo_mc._visible = true;
         this.transport_mc._visible = false;
         this.dispatchEvent({type:"control",marks:false,players:true});
         lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.LABEL_OR_PLAYERS,"player");
      }
      else if(obj.target == this.marks_btn)
      {
         this.users_btn.toggled = false;
         this.marks_btn.toggled = true;
         this.trans_btn.toggled = false;
         this.userList_mc._visible = false;
         this.markList_mc._visible = true;
         this.userInfo_mc._visible = false;
         this.markInfoPan._visible = true;
         this.transport_mc._visible = false;
         this.dispatchEvent({type:"control",marks:true,players:false});
         lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.LABEL_OR_PLAYERS,"label");
      }
      else if(obj.target == this.trans_btn)
      {
         this.users_btn.toggled = false;
         this.marks_btn.toggled = false;
         this.trans_btn.toggled = true;
         this.userList_mc._visible = false;
         this.markList_mc._visible = false;
         this.userInfo_mc._visible = false;
         this.markInfoPan._visible = false;
         this.transport_mc._visible = true;
         this.dispatchEvent({type:"control",marks:false,players:false});
         lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.LABEL_OR_PLAYERS,"transport");
      }
   }
}
