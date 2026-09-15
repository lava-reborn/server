class lol.gpui.InspectInterface extends lol.gpui.StaffInterface
{
   var close_btn;
   var dispatchEvent;
   var doLater;
   var equipment;
   var gotoAndStop;
   var initSlot;
   var inspectBM_btn;
   var inspectBM_mc;
   var outfit_mc;
   var player;
   var publicListPan;
   var slots;
   var trophyBM_btn;
   var trophyBM_mc;
   function InspectInterface()
   {
      super();
      this.doLater("init");
      this.slots = new Array();
      this.slots.primary = this.outfit_mc.prim_mc;
      this.slots.secondary = this.outfit_mc.sec_mc;
      this.slots.head = this.outfit_mc.head_mc;
      this.slots.armor = this.outfit_mc.armor_mc;
      this.slots.camouflage = this.outfit_mc.cam_mc;
      this.slots.legs = this.outfit_mc.legs_mc;
      this.slots.boots = this.outfit_mc.boots_mc;
      this.slots.belt = this.outfit_mc.belt_mc;
      this.inspectBM_mc.enabled = false;
      this.trophyBM_mc.enabled = false;
      this.trophyBM_mc._visible = false;
      this.inspectBM_btn._visible = false;
   }
   function setPlayer(id)
   {
      this.player = lol.core.player.Player(lol.core.Master.getInstance().getPlayer(id));
      this.equipment = this.player.equipment;
      this.equipment.parseWear();
   }
   function init()
   {
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.inspectBM_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showInspect);
      this.trophyBM_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showTrophy);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.equipment.addEventListener("requestPublicTrophy",this,this.setPublicTrophyList);
      lol.core.SceneShifter.hotKeyManager.addFilter("cancel");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      this.initObjects();
   }
   function kill()
   {
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.inspectBM_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showInspect);
      this.trophyBM_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showTrophy);
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.equipment.removeEventListener("requestPublicTrophy",this,this.setPublicTrophyList);
      lol.core.SceneShifter.hotKeyManager.removeFilter("cancel");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      this.outfit_mc.kill();
   }
   function close()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function initObjects()
   {
      this.outfit_mc.setPlayer(this.player);
      this.initSlot("primary");
      this.initSlot("secondary");
      this.initSlot("head");
      this.initSlot("armor");
      this.initSlot("camouflage");
      this.initSlot("legs");
      this.initSlot("boots");
      this.initSlot("belt");
   }
   function initTrophy()
   {
      this.equipment.requestPublicTrophy();
   }
   function setPublicTrophyList(obj)
   {
      var _loc10_ = this.equipment.publicTrophy_arr;
      this.publicListPan.setSize(520,335);
      var _loc7_ = this.publicListPan.fillContent();
      var _loc6_ = 0;
      var _loc3_ = 0;
      var _loc11_ = _loc10_.length <= 12 ? 12 : _loc10_.length;
      var _loc2_ = 0;
      var _loc4_;
      var _loc5_;
      while(_loc2_ < _loc11_)
      {
         _loc4_ = _loc10_[_loc2_];
         _loc5_ = lol.gpui.SlotPan(_loc7_.attachMovie("trophySlotPan","trophySlotPan" + _loc2_,_loc7_.getNextHighestDepth(),{_x:_loc3_ * 170,_y:_loc6_ * 85}));
         if(_loc4_)
         {
            _loc5_.addItem(_loc4_);
         }
         if(_loc3_ < 2)
         {
            _loc3_ = _loc3_ + 1;
         }
         else
         {
            _loc3_ = 0;
            _loc6_ = _loc6_ + 1;
         }
         _loc2_ = _loc2_ + 1;
      }
      this.publicListPan.chekSize();
      this.publicListPan._visible = true;
   }
   function showInspect()
   {
      this.gotoAndStop(1);
      this.trophyBM_btn._visible = true;
      this.trophyBM_mc._visible = false;
      this.inspectBM_mc._visible = true;
      this.inspectBM_btn._visible = false;
      this.outfit_mc.setPlayer(this.player);
      this.doLater("initObjects");
   }
   function showTrophy()
   {
      this.gotoAndStop(2);
      this.trophyBM_btn._visible = false;
      this.trophyBM_mc._visible = true;
      this.inspectBM_mc._visible = false;
      this.inspectBM_btn._visible = true;
      this.publicListPan._visible = false;
      this.doLater("initTrophy");
   }
}
