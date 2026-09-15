class lol.gpui.SupportInterface extends lol.gpui.GPUIObject
{
   var apply_btn;
   var close_btn;
   var desc_txt;
   var dispatchEvent;
   var master;
   var moneyPan;
   var selectedAttendance;
   var supportList_lp;
   function SupportInterface()
   {
      super();
      this.doLater("init");
      lol.core.SceneShifter.locationScreen.centerChar();
   }
   function init()
   {
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.master = lol.core.Master.getInstance();
      this.showMoney(this.master.gamer.attributes.afro);
      this.supportList_lp.setSize(200,300);
      this.desc_txt.text = "";
      this.desc_txt.autoSize = true;
      this.desc_txt.wordWrap = true;
      this.apply_btn._visible = false;
      this.apply_btn.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.applyAttendance);
      this.master.gamer.addEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
      this.createSupportList();
      lol.core.SceneShifter.hotKeyManager.addFilter("cancel");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
   }
   function close()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function kill()
   {
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.apply_btn.removeEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.applyAttendance);
      this.master.gamer.removeEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
      lol.core.SceneShifter.hotKeyManager.removeFilter("cancel");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
   }
   function createSupportList()
   {
      var _loc8_ = this.master.gamer.servicer;
      var _loc5_ = _loc8_.getSupport();
      var _loc2_ = 0;
      var _loc3_;
      var _loc4_;
      while(_loc2_ < _loc5_.length)
      {
         _loc3_ = _loc5_[_loc2_];
         _loc4_ = this.supportList_lp.addItem({label:_loc3_.name,data:_loc3_});
         _loc4_.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.selectAttendance);
         _loc4_.setStyle(lol.gpui.controls.GPUIButton.lavaStyle1);
         _loc2_ = _loc2_ + 1;
      }
      var _loc9_ = new lol.utils.Timeout(this,this.setStyle,1000);
   }
   function setStyle()
   {
      var _loc2_ = this.supportList_lp.getList();
      for(var _loc3_ in _loc2_)
      {
         _loc2_[_loc3_].setStyle(lol.gpui.controls.GPUIButton.lavaStyle1);
      }
   }
   function selectAttendance(obj)
   {
      var _loc2_ = obj.target;
      if(_loc2_.toggled)
      {
         this.selectedAttendance = lol.core.player.Attendance(_loc2_.data);
         this.desc_txt.text = this.selectedAttendance.description;
         this.apply_btn._visible = true;
         this.apply_btn._y = this.desc_txt._y + this.desc_txt._height + 5;
      }
      else
      {
         this.selectedAttendance = null;
         this.desc_txt.text = "";
         this.apply_btn._visible = false;
      }
   }
   function applyAttendance()
   {
      this.selectedAttendance.activate();
   }
   function userInfoUpdate(obj)
   {
      var _loc2_ = lol.core.Master.getInstance();
      this.showMoney(_loc2_.gamer.attributes.afro);
   }
   function showMoney(afro)
   {
      this.moneyPan.value = afro;
   }
}
