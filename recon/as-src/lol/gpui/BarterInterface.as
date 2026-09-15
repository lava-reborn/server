class lol.gpui.BarterInterface extends lol.gpui.StaffInterface
{
   var _xmouse;
   var _ymouse;
   var attachMovie;
   var bagInfo_txt;
   var bag_mc;
   var barter;
   var close_btn;
   var currDDOperation;
   var currentBag;
   var ddOperation_arr;
   var dispatchEvent;
   var doLater;
   var dragItemMc;
   var dragNdrop;
   var dropTarget;
   var exchangeMainSize;
   var exchangePanCost_num;
   var exchangePan_cost_mod;
   var exchangePan_showCostInGold;
   var filterPan;
   var getAfro_txt;
   var getGold_txt;
   var listIconPan;
   var lite1_mc;
   var lite2_mc;
   var master;
   var moneyPan_mc;
   var myBarterInfo_txt;
   var myBarter_mc;
   var my_btn;
   var my_txt;
   var onMouseMove;
   var priceEnabled;
   var slots;
   var sortMask;
   var vAfro_txt;
   var vGold_txt;
   var vav_txt;
   var visavisBarterInfo_txt;
   var visavisBarter_mc;
   var weightPan;
   var goldOperation_bool = false;
   var ddFlag = false;
   function BarterInterface()
   {
      super();
      lol.gpui.StaffInterface.ssType = lol.gpui.StaffInterface.SS_BARTER;
      this.doLater("init");
      this.slots = new Array();
      this.slots.bag = this.bag_mc;
      this.slots.myBarterList = this.myBarter_mc;
      this.slots.visavisBarterList = this.visavisBarter_mc;
      this.bag_mc.id = "bag";
      this.myBarter_mc.id = "myBarterList";
      this.visavisBarter_mc.id = "visavisBarterList";
      this.master = lol.core.Master.getInstance();
      lol.core.SceneShifter.locationScreen.centerChar();
   }
   function init()
   {
      if(!this.goldOperation_bool)
      {
         this.moneyPan_mc.gotoAndStop(2);
      }
      this.getAfro_txt = this.moneyPan_mc.getAfro_txt;
      this.getGold_txt = this.moneyPan_mc.getGold_txt;
      this.vAfro_txt = this.moneyPan_mc.vAfro_txt;
      this.vGold_txt = this.moneyPan_mc.vGold_txt;
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      var _loc2_ = lol.core.Master.getInstance();
      this.barter = _loc2_.gamer.barter;
      this.barter.addEventListener("close",this,this.barterClose);
      this.getAfro_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKeys);
      this.getAfro_txt.onKillFocus = mx.utils.Delegate.create(this,this.unblockHotKeys);
      this.getGold_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKeys);
      this.getGold_txt.onKillFocus = mx.utils.Delegate.create(this,this.unblockHotKeys);
      this.sortMask = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_MASK_BARTER);
      this.bag_mc.sortMask = this.sortMask;
      this.bag_mc.alignEnabled = true;
      this.bag_mc.addEventListener("changeMask",this,this.changeMaskBag);
      this.filterPan.addEventListener("changeMask",this);
      this.filterPan.init(this.sortMask);
      this.dropTarget = this.barter;
      _loc2_.gamer.equipment.addEventListener("addItem",this);
      _loc2_.gamer.equipment.addEventListener("removeItem",this);
      this.barter.addEventListener("addItem",this);
      this.barter.addEventListener("removeItem",this);
      this.barter.addEventListener(lol.gpui.DDEvents.TRANSFER_ERROR,this,this.moveItemError);
      this.barter.addEventListener(lol.gpui.DDEvents.TRANSFER_SUCCESS,this,this.moveItemSuccess);
      this.barter.addEventListener("separate",this,this.separateAck);
      this.barter.addEventListener("ready",this);
      this.barter.addEventListener("visavisMUpdate",this);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.bag_mc.addEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.addEventListener("removeItem",this,this.bagRemoveItem);
      this.bag_mc.addEventListener("bagActive",this,this.bagActive);
      this.myBarter_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.myBarter_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.myBarter_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.myBarter_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.myBarter_mc.addEventListener("addItem",this,this.bagAddItem);
      this.myBarter_mc.addEventListener("removeItem",this,this.bagRemoveItem);
      this.myBarter_mc.addEventListener("bagActive",this,this.bagActive);
      this.visavisBarter_mc.addEventListener("addItem",this,this.bagAddItem);
      this.visavisBarter_mc.addEventListener("removeItem",this,this.bagRemoveItem);
      lol.core.SceneShifter.hotKeyManager.addFilter("barter");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.SELECT_ALL,this,this.selectAll);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      this.my_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.myClick);
      this.bag_mc.bagPan.setSize(185,332);
      this.myBarter_mc.bagPan.setSize(185,332);
      this.visavisBarter_mc.bagPan.setSize(185,332);
      this.bagInfo_txt.text = "0";
      this.listIconPan.addEventListener("changeView",this);
      this.typeOfList = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.TYPE_OF_LIST_BARTER);
      this.listIconPan.init(this.typeOfList);
      this.bag_mc.typeOfList = this.typeOfList;
      this.visavisBarter_mc.typeOfList = this.typeOfList;
      this.myBarter_mc.typeOfList = this.typeOfList;
      this.initObjects();
      this.initMoney();
   }
   function barterClose()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function close()
   {
      this.barter.close();
      this.dispatchEvent({type:"closeWindow"});
   }
   function kill()
   {
      this.bag_mc.kill();
      this.myBarter_mc.kill();
      this.visavisBarter_mc.kill();
      this.filterPan.kill();
      this.filterPan.removeEventListener("changeMask",this);
      this.listIconPan.kill();
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.master.gamer.equipment.removeEventListener("addItem",this);
      this.master.gamer.equipment.removeEventListener("removeItem",this);
      this.barter.removeEventListener("addItem",this);
      this.barter.removeEventListener("removeItem",this);
      this.barter.removeEventListener("ready",this);
      this.barter.removeEventListener("visavisMUpdate",this);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.bag_mc.removeEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.removeEventListener("removeItem",this,this.bagRemoveItem);
      this.bag_mc.removeEventListener("bagActive",this,this.bagActive);
      this.myBarter_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.myBarter_mc.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.myBarter_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.myBarter_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.myBarter_mc.removeEventListener("addItem",this,this.bagAddItem);
      this.myBarter_mc.removeEventListener("removeItem",this,this.bagRemoveItem);
      this.myBarter_mc.removeEventListener("bagActive",this,this.bagActive);
      this.visavisBarter_mc.removeEventListener("addItem",this,this.bagAddItem);
      this.visavisBarter_mc.removeEventListener("removeItem",this,this.bagRemoveItem);
      this.my_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.myClick);
      lol.core.SceneShifter.hotKeyManager.removeFilter("barter");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.SELECT_ALL,this,this.selectAll);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      lol.core.SceneShifter.closeWindow("annotation","all");
   }
   function blockHotKeys()
   {
      lol.core.SceneShifter.hotKeyManager.enabled = false;
   }
   function unblockHotKeys()
   {
      lol.core.SceneShifter.hotKeyManager.enabled = true;
   }
   function initObjects()
   {
      this.initBag(this.barter.bag);
      this.initBag(this.barter.myBarterList);
      this.initBag(this.barter.visavisBarterList);
   }
   function clearObjects()
   {
      this.clearBag(this.barter.bag);
      this.clearBag(this.barter.myBarterList);
      this.clearBag(this.barter.visavisBarterList);
      this.bag_mc.firstAttaching = true;
      this.myBarter_mc.firstAttaching = true;
      this.visavisBarter_mc.firstAttaching = true;
   }
   function changeView(obj)
   {
      if(!this.bag_mc.attaching && !this.myBarter_mc.attaching && !this.visavisBarter_mc.attaching)
      {
         lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.TYPE_OF_LIST_BARTER,obj.typeOfList);
         this.clearObjects();
         this.typeOfList = obj.typeOfList;
         this.bag_mc.typeOfList = obj.typeOfList;
         this.myBarter_mc.typeOfList = obj.typeOfList;
         this.visavisBarter_mc.typeOfList = obj.typeOfList;
         this.doLater("initObjects");
      }
      else
      {
         this.listIconPan._typeOfList();
      }
   }
   function bagActive(obj)
   {
      var _loc3_ = obj.status;
      if(_loc3_)
      {
         this.currentBag = obj.target;
      }
      else if(this.currentBag == obj.target)
      {
         this.currentBag = null;
      }
   }
   function selectAll()
   {
      this.currentBag.selectAll();
   }
   function showVisavisAvatar()
   {
   }
   function checkAnswer(obj)
   {
      obj.target.removeEventListener("click",this,this.checkAnswer);
      lol.core.SceneShifter.closeWindow("query");
      var _loc2_ = obj.success;
      this.barter.readyToBarter(_loc2_);
   }
   function myClick(obj)
   {
      var _loc2_ = obj.target;
      var _loc4_;
      var _loc5_;
      var _loc3_;
      if(_loc2_.toggled)
      {
         _loc4_ = this.weightPan.getMaxWeight();
         _loc5_ = this.weightPan.getCurWeight();
         if(_loc5_ + this.visavisBarter_mc.getTotalItemWeight() - this.myBarter_mc.getTotalItemWeight() > _loc4_)
         {
            _loc3_ = lol.core.SceneShifter.openNewWindow("query");
            _loc3_.content.label = "После этого бартера вы будете перегружены!\nИ шо, вам-таки это надо? ;-)";
            _loc3_.content.addEventListener("click",this,this.checkAnswer);
         }
         else
         {
            this.readyToBarter(_loc2_.toggled);
         }
      }
      else
      {
         this.readyToBarter(_loc2_.toggled);
      }
   }
   function readyToBarter(ready)
   {
      this.barter.readyToBarter(ready);
   }
   function ready(obj)
   {
      var _loc2_ = obj.i_ready;
      var _loc3_ = obj.vav_ready;
      if(_loc3_)
      {
         this.lite2_mc.gotoAndStop(2);
      }
      else
      {
         this.vav_txt.text = "";
         this.lite2_mc.gotoAndStop(1);
      }
      if(_loc2_)
      {
         this.my_btn.toggled = true;
         this.lite1_mc.gotoAndStop(2);
      }
      else
      {
         this.my_txt.text = "";
         this.my_btn.toggled = false;
         this.lite1_mc.gotoAndStop(1);
      }
   }
   function _mouseUp(obj)
   {
      if(this.dragNdrop.from.id == "bag" && obj.target.id == "bag")
      {
         super._mouseUp(obj);
      }
      else if(this.dropEnabled)
      {
         delete this.onMouseMove;
         this.dragNdrop.where = obj.target;
      }
   }
   function startDragNDrop(obj)
   {
      if(!this.ddOperation_arr)
      {
         this.ddOperation_arr = new Array();
      }
      this.ddFlag = true;
      var _loc2_ = obj.item_arr;
      var _loc4_ = obj.target;
      for(var _loc3_ in _loc2_)
      {
         _loc2_[_loc3_].blockItem();
      }
      if(_loc2_.length > 1)
      {
         this.createDragItemMc(_loc2_[0].item,true);
      }
      else
      {
         this.createDragItemMc(_loc2_[0].item);
      }
      this.currDDOperation = new lol.gpui.DDOperation();
      this.currDDOperation.setFrom(_loc2_[0].item,_loc4_,_loc2_[0],_loc2_);
   }
   function createDragItemMc(_item, group)
   {
      if(this.typeOfList == "icon")
      {
         this.dragItemMc = lol.gpui.ItemContainer(this.attachMovie("itemCont","dd",10));
         this.dragItemMc.attachIconEnabled = true;
      }
      else if(this.typeOfList == "list")
      {
         this.dragItemMc = lol.gpui.ItemContainer(this.attachMovie("listItemCont","dd",10));
         this.dragItemMc.attachIconEnabled = false;
      }
      this.dragItemMc.priceEnabled = this.priceEnabled;
      this.dragItemMc.showItemRepairMod = this.showItemRepairMod;
      this.dragItemMc.cost_mod = this.cost_mod;
      this.dragItemMc.groupItem = group;
      this.dragItemMc.item = _item;
      this.dragItemMc.attachIcon(_item);
      this.draggingItem();
      this.onMouseMove = this.draggingItem;
   }
   function draggingItem()
   {
      this.dragItemMc._x = Math.round(this._xmouse - this.dragItemMc._width / 2);
      this.dragItemMc._y = Math.round(this._ymouse - this.dragItemMc._height / 2);
   }
   function doubleClick(obj)
   {
      if(!this.ddOperation_arr)
      {
         this.ddOperation_arr = new Array();
      }
      var _loc2_ = obj.item_mc;
      _loc2_.blockItem();
      this.currDDOperation = new lol.gpui.DDOperation();
      this.currDDOperation.setFrom(_loc2_.item,obj.target,_loc2_);
      var _loc3_;
      if(obj.target == this.bag_mc)
      {
         this.currDDOperation.setTo(0,this.myBarter_mc);
         if(lol.core.objects.Heapable(this.currDDOperation.fromItem).heapSize > 1 && this.currDDOperation.fromItem instanceof lol.core.objects.Heapable)
         {
            _loc3_ = this.createExchangePan(this.currDDOperation.fromItem,"Сколько штук положить?");
            _loc3_.addEventListener("exchange",this,this.exchangeDropAck);
            _loc3_.addEventListener("close",this,this.exchangeCancel);
         }
         else
         {
            this.sendTransferToServer();
         }
      }
      else
      {
         this.currDDOperation.setTo(0,this.bag_mc);
         this.sendTransferToServer();
      }
   }
   function mouseUpOnItem(obj)
   {
      var _loc2_;
      if(this.ddFlag)
      {
         _loc2_ = obj.item_mc;
         this.currDDOperation.setTo(_loc2_.item,obj.target,_loc2_);
      }
   }
   function dropItem(obj)
   {
      var _loc2_;
      if(this.ddFlag)
      {
         _loc2_ = obj.target;
         this.currDDOperation.setTo(0,_loc2_);
      }
   }
   function onMouseUp()
   {
      var _loc2_;
      if(this.ddFlag)
      {
         this.ddFlag = false;
         this.dragItemMc.kill();
         this.dragItemMc.removeMovieClip();
         if(this.currDDOperation.toSlot)
         {
            if(!this.currDDOperation.group && lol.core.objects.Heapable(this.currDDOperation.fromItem).heapSize > 1 && this.currDDOperation.fromItem instanceof lol.core.objects.Heapable && this.currDDOperation.fromSlot == this.bag_mc && this.currDDOperation.toSlot == this.myBarter_mc)
            {
               _loc2_ = this.createExchangePan(this.currDDOperation.fromItem,"Сколько штук положить?");
               _loc2_.addEventListener("exchange",this,this.exchangeDropAck);
               _loc2_.addEventListener("close",this,this.exchangeCancel);
            }
            else
            {
               this.sendTransferToServer();
            }
         }
         else
         {
            this.moveItemError();
         }
      }
      delete this.onMouseMove;
   }
   function sendTransferToServer()
   {
      var _loc3_ = this.currDDOperation.fromItemMc_arr;
      var _loc4_;
      var _loc2_;
      if(_loc3_)
      {
         for(var _loc5_ in _loc3_)
         {
            _loc2_ = new lol.gpui.DDOperation();
            _loc2_.setFrom(_loc3_[_loc5_].item,this.currDDOperation.fromSlot,_loc3_[_loc5_]);
            _loc2_.setTo(this.currDDOperation.toItem,this.currDDOperation.toSlot,this.currDDOperation.toItemMc);
            if(this.checkSellItem(_loc2_.fromItem) && this.currDDOperation.toSlot == this.myBarter_mc && this.currDDOperation.fromSlot == this.bag_mc)
            {
               _loc4_ = this.checkSellItem(_loc2_.fromItem);
               _loc2_.failedOperation();
            }
            else
            {
               this.ddOperation_arr.push(_loc2_);
               this.barter.transferItem(_loc2_.fromItem,_loc2_.fromSlot.id,_loc2_.toSlot.id,_loc2_.toItem);
            }
         }
      }
      else if(this.checkSellItem(this.currDDOperation.fromItem) && this.currDDOperation.toSlot == this.myBarter_mc && this.currDDOperation.fromSlot == this.bag_mc)
      {
         _loc4_ = this.checkSellItem(this.currDDOperation.fromItem);
         this.currDDOperation.failedOperation();
      }
      else
      {
         this.ddOperation_arr.push(this.currDDOperation);
         this.barter.transferItem(this.currDDOperation.fromItem,this.currDDOperation.fromSlot.id,this.currDDOperation.toSlot.id,this.currDDOperation.toItem);
      }
      var _loc6_;
      if(_loc4_)
      {
         _loc6_ = lol.core.SceneShifter.openNewWindow("alert");
         _loc6_.content.label = _loc4_;
      }
      delete this.currDDOperation;
   }
   function sendHeapToServer()
   {
      this.ddOperation_arr.push(this.currDDOperation);
      this.barter.separateHeap(lol.core.objects.Heapable(this.currDDOperation.fromItem),this.currDDOperation.heapNum);
      delete this.currDDOperation;
   }
   function checkSellItem(_item)
   {
      var _loc2_;
      var _loc3_ = _item.getProp("__break");
      var _loc1_ = _item.getProp("exchang");
      if(!_loc1_)
      {
         _loc2_ = "Вы не можете передать некоторые предметы";
      }
      return _loc2_;
   }
   function moveItemSuccess()
   {
      var _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      _loc2_.successOperation();
   }
   function moveItemError()
   {
      var _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      _loc2_.failedOperation();
      this.currDDOperation.failedOperation();
      delete this.currDDOperation;
   }
   function createExchangePan(_item, title_str)
   {
      var _loc3_ = lol.core.objects.Heapable(_item);
      var _loc4_ = lol.core.SceneShifter.openNewWindow("exchange");
      var _loc2_ = lol.gpui.ExchangePan(_loc4_.content);
      _loc2_.label = title_str;
      _loc2_.mainSize = this.exchangeMainSize;
      _loc2_.cost_num = this.exchangePanCost_num;
      _loc2_.cost_mod = this.exchangePan_cost_mod;
      _loc2_.showCostInGold = this.exchangePan_showCostInGold;
      _loc2_.maxValue = _loc3_.heapSize;
      this.dropEnabled = false;
      return _loc2_;
   }
   function exchangeDropAck(obj)
   {
      obj.target.removeEventListener("close",this,this.exchangeCancel);
      obj.target.removeEventListener("exchange",this,this.exchangeDropAck);
      lol.core.SceneShifter.closeWindow("exchange");
      if(lol.core.objects.Heapable(this.currDDOperation.fromItem).heapSize == obj.right)
      {
         this.sendTransferToServer();
      }
      else
      {
         this.currDDOperation.heapNum = obj.left;
         this.sendHeapToServer();
      }
   }
   function exchangeCancel(obj)
   {
      obj.target.removeEventListener("close",this,this.exchangeCancel);
      obj.target.removeEventListener("exchange",this,this.exchangeDropAck);
      lol.core.SceneShifter.closeWindow("exchange");
      this.moveItemError();
      delete this.currDDOperation;
   }
   function separateAck(obj)
   {
      var _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      if(obj.res == 0)
      {
         _loc2_.successOperation();
         if(_loc2_.fromSlot == this.bag_mc && _loc2_.toSlot == this.myBarter_mc)
         {
            _loc2_.fromItemMc.blockItem();
            this.currDDOperation = new lol.gpui.DDOperation();
            this.currDDOperation.setFrom(_loc2_.fromItem,_loc2_.fromSlot,_loc2_.fromItemMc);
            this.currDDOperation.setTo(0,this.myBarter_mc);
            this.sendTransferToServer();
         }
      }
      else
      {
         _loc2_.failedOperation();
      }
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
      _loc2_ = this.myBarter_mc.sortList.length;
      _loc2_ = _loc2_ != undefined ? _loc2_ : 0;
      this.myBarterInfo_txt.text = _loc2_;
      this.myBarterInfo_txt.setTextFormat(_loc3_);
      _loc2_ = this.visavisBarter_mc.sortList.length;
      _loc2_ = _loc2_ != undefined ? _loc2_ : 0;
      this.visavisBarterInfo_txt.text = _loc2_;
      this.visavisBarterInfo_txt.setTextFormat(_loc3_);
   }
   function changeMaskBag(obj)
   {
      this.sortMask = obj.sortMask;
      this.filterPan.sortMaskToggled(this.sortMask);
   }
   function changeMask(obj)
   {
      this.sortMask = obj.sortMask;
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SORT_MASK_BARTER,this.sortMask);
      this.bag_mc.sortMask = this.sortMask;
      this.bag_mc.resort();
      this.doLater("bagInfo",["bag"]);
   }
   function initMoney()
   {
      var _loc2_ = this.master.gamer.attributes.afro;
      var _loc3_ = 0.01 * this.master.gamer.attributes.gold;
      this.getGold_txt.text = String(0);
      this.getAfro_txt.text = String(0);
      this.vAfro_txt.text = String(0);
      this.vGold_txt.text = String(0);
      this.getAfro_txt.onChanged = mx.utils.Delegate.create(this,this.changeAfro);
      this.getGold_txt.onChanged = mx.utils.Delegate.create(this,this.changeGold);
   }
   function changeAfro()
   {
      var _loc3_ = this.getAfro_txt.text;
      _loc3_ = this.replaceNulls(_loc3_);
      this.getAfro_txt.text = _loc3_;
      var _loc2_ = Number(_loc3_);
      var _loc4_ = this.master.gamer.attributes.afro;
      if(this.getAfro_txt.text == "" || isNaN(_loc2_))
      {
         _loc2_ = 0;
         this.getAfro_txt.text = String(0);
      }
      if(_loc2_ >= _loc4_)
      {
         _loc2_ = _loc4_;
         this.getAfro_txt.text = String(_loc4_);
      }
      _loc2_ = Number(this.getAfro_txt.text);
      this.barter.addMoney(_loc2_,"afro");
      this.readyToBarter(false);
   }
   function changeGold()
   {
      var _loc2_ = this.getGold_txt.text;
      _loc2_ = lol.utils.ParseString.replaceAll(_loc2_,",",".");
      _loc2_ = this.replaceNulls(_loc2_);
      if(_loc2_.charAt(0) == ".")
      {
         _loc2_ = "0" + _loc2_;
      }
      this.getGold_txt.text = _loc2_;
      var _loc5_ = _loc2_.charAt(_loc2_.length);
      if(_loc5_ == ".")
      {
         _loc2_ = _loc2_.substring(0,_loc2_.length);
      }
      var _loc3_ = Number(_loc2_);
      var _loc4_ = 0.01 * this.master.gamer.attributes.gold;
      if(this.getGold_txt.text == "" || isNaN(_loc3_))
      {
         _loc3_ = 0;
         this.getGold_txt.text = String(0);
      }
      if(_loc3_ * 100 % 1 > 0)
      {
         _loc3_ = 0.01 * Math.floor(_loc3_ * 100);
         this.getGold_txt.text = String(_loc3_);
      }
      if(_loc3_ >= _loc4_)
      {
         _loc3_ = _loc4_;
         this.getGold_txt.text = String(_loc4_);
      }
      _loc3_ = 100 * Number(this.getGold_txt.text);
      this.barter.addMoney(_loc3_,"gold");
      this.readyToBarter(false);
   }
   function replaceNulls(str)
   {
      var _loc2_;
      var _loc1_ = -1;
      var _loc5_ = false;
      var _loc4_;
      if(str.charAt(0) == "0" && str.charAt(1) != ".")
      {
         while(!_loc2_)
         {
            _loc1_ = _loc1_ + 1;
            _loc4_ = str.charAt(_loc1_);
            if(_loc4_ == "0")
            {
               _loc5_ = true;
            }
            else
            {
               _loc2_ = true;
            }
            if(_loc1_ >= str.length)
            {
               _loc2_ = true;
            }
         }
      }
      if(_loc5_)
      {
         str = str.substring(_loc1_,str.length);
      }
      return str;
   }
   function visavisMUpdate(obj)
   {
      var _loc4_ = obj.mtype;
      var _loc3_ = obj.value;
      var _loc2_;
      if(_loc4_ == "afro")
      {
         _loc2_ = String(_loc3_);
         _loc2_ = _loc2_ != "NaN" ? _loc2_ : 0;
         this.vAfro_txt.text = _loc2_;
      }
      else if(_loc4_ == "gold")
      {
         _loc2_ = String(0.01 * _loc3_);
         _loc2_ = _loc2_ != "NaN" ? _loc2_ : 0;
         this.vGold_txt.text = _loc2_;
      }
   }
}
