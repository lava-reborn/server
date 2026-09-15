class lol.gpui.UpgradeInterface extends lol.gpui.StaffInterface
{
   var ab0;
   var addItem;
   var bagInfo_txt;
   var bag_mc;
   var close_btn;
   var dispatchEvent;
   var doLater;
   var dragNdrop;
   var dropTarget;
   var filterPan;
   var listIconPan;
   var master;
   var moneyPan;
   var slots;
   var sortMask;
   var tradeBagInfo_txt;
   var typeOfList;
   var upgrade;
   var visavisBag_mc;
   var visavisPan;
   function UpgradeInterface()
   {
      super();
      lol.gpui.StaffInterface.ssType = lol.gpui.StaffInterface.SS_UPGRADE;
      this.doLater("init");
      this.slots = new Array();
      this.slots.bag = this.bag_mc;
      this.slots.visavisBag = this.visavisBag_mc;
      this.bag_mc.id = "bag";
      this.visavisBag_mc.id = "visavisBag";
      lol.core.SceneShifter.locationScreen.centerChar();
   }
   function init()
   {
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.master = lol.core.Master.getInstance();
      this.upgrade = this.master.gamer.upgrade;
      this.upgrade.addEventListener("close",this,this.upgradeClose);
      this.master.gamer.addEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
      if(this.sortMask == undefined)
      {
         this.sortMask = [1,1,1,1,1,1,1,1,1,1,1];
      }
      this.bag_mc.sortMask = this.sortMask;
      this.bag_mc.alignEnabled = true;
      this.bag_mc.dragEnabled = false;
      this.bag_mc.selectGroupAvailable = false;
      this.bag_mc.unselectClickOut = false;
      this.bag_mc.lostFocus = false;
      this.bag_mc.addEventListener("changeMask",this,this.changeMaskBag);
      this.filterPan.addEventListener("changeMask",this);
      this.filterPan.init(this.sortMask);
      this.moneyPan.type = "gold";
      this.listIconPan.addEventListener("changeView",this);
      this.typeOfList = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.TYPE_OF_LIST_UPGRADE);
      this.listIconPan.init(this.typeOfList);
      this.bag_mc.typeOfList = this.typeOfList;
      this.visavisBag_mc.typeOfList = this.typeOfList;
      this.showMoney(this.master.gamer.attributes.gold);
      this.dropTarget = this.upgrade;
      this.master.gamer.equipment.addEventListener("addItem",this,this.upgradeAddItem);
      this.master.gamer.equipment.addEventListener("removeItem",this,this.upgradeRemoveItem);
      this.bag_mc.addEventListener("_mouseDown",this);
      this.bag_mc.addEventListener("_mouseUp",this);
      this.bag_mc.addEventListener("shiftMouseDown",this);
      this.bag_mc.addEventListener("ctrlMouseDown",this);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.SELECT,this,this.selectItem);
      this.bag_mc.addEventListener("attaching",this,this.bagAttaching);
      this.bag_mc.handSortMask = [1,1,1,1,1,1,1,1,0,0,0];
      this.bag_mc.handAlign = true;
      this.bag_mc.selectGroupAvailable = false;
      this.bag_mc.dragEnabled = false;
      this.bag_mc.addEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.addEventListener("removeItem",this,this.bagRemoveItem);
      this.visavisPan.fillContent();
      this.visavisPan.setSize(185,330);
      this.bag_mc.bagPan.setSize(185,330);
      lol.core.SceneShifter.hotKeyManager.addFilter("cancel");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      this.doLater("initObjects");
   }
   function upgradeClose()
   {
      this.close();
   }
   function close()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function kill()
   {
      this.bag_mc.kill();
      this.visavisBag_mc.kill();
      this.filterPan.kill();
      this.filterPan.removeEventListener("changeMask",this);
      this.listIconPan.kill();
      this.listIconPan.removeEventListener("changeView",this);
      this.master.gamer.removeEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
      this.master.gamer.equipment.removeEventListener("addItem",this,this.upgradeAddItem);
      this.master.gamer.equipment.removeEventListener("removeItem",this);
      this.upgrade.removeEventListener("addItem",this,this.upgradeAddItem);
      this.upgrade.removeEventListener("removeItem",this);
      this.bag_mc.removeEventListener("_mouseDown",this);
      this.bag_mc.removeEventListener("_mouseUp",this);
      this.bag_mc.removeEventListener("shiftMouseDown",this);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.SELECT,this,this.selectItem);
      this.bag_mc.removeEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.removeEventListener("removeItem",this,this.bagRemoveItem);
      this.bag_mc.removeEventListener("attaching",this,this.bagAttaching);
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.upgrade.removeEventListener("close",this,this.upgradeClose);
      this.upgrade.close();
      lol.core.SceneShifter.closeWindow("annotation","all");
      lol.core.SceneShifter.hotKeyManager.removeFilter("cancel");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      super.kill();
   }
   function bagAttaching(obj)
   {
      var _loc2_ = obj.proc;
      this.ab0._xscale = _loc2_;
   }
   function upgradeAddItem(obj)
   {
      var _loc3_ = obj.item;
      var _loc2_ = this.upgrade.neededList;
      for(var _loc5_ in _loc2_)
      {
         if(_loc3_.typeID == _loc2_[_loc5_])
         {
            this.addItem(obj);
            break;
         }
      }
   }
   function upgradeRemoveItem(obj)
   {
      var _loc2_ = obj.item;
      this.bag_mc.removeItem(_loc2_);
   }
   function initObjects()
   {
      var _loc3_ = this.upgrade.neededList;
      var _loc4_ = this.upgrade.bag.itemList;
      var _loc2_;
      for(var _loc6_ in _loc4_)
      {
         _loc2_ = _loc4_[_loc6_];
         for(var _loc5_ in _loc3_)
         {
            if(_loc2_.typeID == _loc3_[_loc5_])
            {
               this.bag_mc.addItem(_loc2_,null);
               break;
            }
         }
      }
   }
   function clearObjects()
   {
      this.bag_mc.removeAllItems();
      this.bag_mc.firstAttaching = true;
      this.visavisBag_mc.firstAttaching = true;
   }
   function changeView(obj)
   {
      if(!this.bag_mc.attaching)
      {
         lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.TYPE_OF_LIST_UPGRADE,obj.typeOfList);
         this.clearObjects();
         this.typeOfList = obj.typeOfList;
         this.bag_mc.typeOfList = obj.typeOfList;
         this.visavisBag_mc.typeOfList = obj.typeOfList;
         this.doLater("initObjects");
      }
      else
      {
         this.listIconPan._typeOfList();
      }
   }
   function addDescription(item)
   {
      var _loc5_ = this.upgrade.neededList;
      var _loc8_ = this.upgrade.upgradedList;
      var _loc4_;
      var _loc3_ = new Array();
      for(var _loc11_ in _loc5_)
      {
         if(_loc5_[_loc11_] == item.typeID)
         {
            _loc4_ = Number(_loc11_);
            _loc3_.push(_loc4_);
         }
      }
      this.visavisPan.fillContent();
      var _loc11_ = 0;
      var _loc9_;
      var _loc10_;
      var _loc2_;
      while(_loc11_ < _loc3_.length)
      {
         _loc9_ = _loc8_[_loc3_[_loc11_]];
         _loc2_ = this.upgrade.visavisBag.getItems();
         for(var _loc7_ in _loc2_)
         {
            if(_loc2_[_loc7_].typeID == _loc9_)
            {
               _loc10_ = _loc2_[_loc7_];
               break;
            }
         }
         this.createUpgradeItem(item,_loc10_);
         _loc11_ = _loc11_ + 1;
      }
      this.visavisPan.setPosition(0,0);
      _loc9_ = _loc8_[_loc4_];
      _loc2_ = this.upgrade.visavisBag.getItems();
      for(_loc11_ in _loc2_)
      {
         if(_loc2_[_loc11_].typeID == _loc9_)
         {
            _loc10_ = _loc2_[_loc11_];
         }
      }
   }
   function createUpgradeItem(beforeItem, afterItem)
   {
      var _loc3_ = this.visavisPan.content;
      var _loc2_ = _loc3_.getNextHighestDepth();
      var _loc4_;
      if(beforeItem.rootID == lol.core.objects.Item.AMMO)
      {
         _loc4_ = _loc3_.attachMovie("upgradeAmmoItem","upgradeAmmoItem" + _loc2_,_loc2_);
      }
      else
      {
         _loc4_ = _loc3_.attachMovie("upgradeItem","upgradeItem" + _loc2_,_loc2_);
      }
      _loc4_.init(beforeItem,afterItem);
      _loc4_._y = _loc3_._height + 20;
      this.doLater("initUpgradeItem",[_loc4_]);
   }
   function initUpgradeItem(mov)
   {
      mov.addEventListener("upgrade",this,this.upgradeFunc);
   }
   function upgradeFunc(obj)
   {
      obj.target.removeEventListener("upgrade",this,this.upgradeFunc);
      var _loc5_ = obj.beforeItem;
      var _loc3_ = obj.afterItem;
      var _loc4_ = obj.num;
      this.upgrade.upgradeItem(_loc5_,_loc3_.typeID,_loc4_);
      this.upgrade.addEventListener("upgrAck",this,this.upgrAck);
   }
   function upgrAck(obj)
   {
      trace("upgrAck!");
      this.upgrade.removeEventListener("upgrAck",this,this.upgrAck);
      var _loc2_;
      var _loc4_;
      var _loc3_;
      if(obj.param.res == "0")
      {
         this.visavisPan.fillContent();
         _loc2_ = this.visavisPan.content;
         _loc4_ = _loc2_.getNextHighestDepth();
         _loc3_ = _loc2_.attachMovie("upgrade_saccess","upgrade_success",_loc4_);
         _loc3_.gotoAndStop(1);
      }
      else
      {
         this.visavisPan.fillContent();
         _loc2_ = this.visavisPan.content;
         _loc4_ = _loc2_.getNextHighestDepth();
         _loc3_ = _loc2_.attachMovie("upgrade_saccess","upgrade_success",_loc4_);
         _loc3_.gotoAndStop(2);
      }
   }
   function userInfoUpdate(obj)
   {
      var _loc2_ = lol.core.Master.getInstance();
      this.showMoney(_loc2_.gamer.attributes.gold);
   }
   function _mouseDown(obj)
   {
      super._mouseDown(obj);
      var _loc3_ = this.dragNdrop.what[0].item;
      this.addDescription(_loc3_);
   }
   function selectItem(obj)
   {
      var _loc2_ = obj.item_mc.item;
      this.addDescription(_loc2_);
   }
   function showMoney(gold)
   {
      this.moneyPan.value = gold;
   }
   function bagAddItem(obj)
   {
      this.doLater("bagInfo");
   }
   function bagRemoveItem(obj)
   {
      this.doLater("bagInfo");
   }
   function bagInfo()
   {
      var _loc3_ = new TextFormat();
      _loc3_.bold = true;
      var _loc2_ = this.bag_mc.sortList.length;
      _loc2_ = _loc2_ != undefined ? _loc2_ : 0;
      this.bagInfo_txt.text = _loc2_;
      this.bagInfo_txt.setTextFormat(_loc3_);
      _loc2_ = this.visavisBag_mc.sortList.length;
      _loc2_ = _loc2_ != undefined ? _loc2_ : 0;
      this.tradeBagInfo_txt.text = _loc2_;
      this.tradeBagInfo_txt.setTextFormat(_loc3_);
   }
   function changeMaskBag(obj)
   {
      this.sortMask = obj.sortMask;
      this.filterPan.sortMaskToggled(this.sortMask);
   }
   function changeMask(obj)
   {
      this.sortMask = obj.sortMask;
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SORT_MASK_UPGRADE,this.sortMask);
      this.bag_mc.sortMask = this.sortMask;
      this.bag_mc.resort();
      this.visavisPan.fillContent();
      this.doLater("bagInfo",["bag"]);
   }
}
