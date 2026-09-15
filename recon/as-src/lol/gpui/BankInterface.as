class lol.gpui.BankInterface extends lol.gpui.StaffInterface
{
   var _xmouse;
   var _ymouse;
   var ab0;
   var ab1;
   var addGold_btn;
   var attachMovie;
   var bagInfo_txt;
   var bag_mc;
   var bank;
   var close_btn;
   var currDDOperation;
   var ddOperation_arr;
   var dispatchEvent;
   var doLater;
   var dragItemMc;
   var dropTarget;
   var exchangeMainSize;
   var exchangePanCost_num;
   var exchangePan_cost_mod;
   var exchangePan_showCostInGold;
   var filterPan;
   var getURL;
   var increaseBank_btn;
   var info_txt;
   var listIconPan;
   var master;
   var onMouseMove;
   var priceEnabled;
   var slots;
   var sortMask;
   var visavisBagInfo_txt;
   var visavisBag_mc;
   var weightPan;
   var ddFlag = false;
   function BankInterface()
   {
      super();
      this.slots = new Array();
      this.slots.bag = this.bag_mc;
      this.slots.visavisBag = this.visavisBag_mc;
      this.bag_mc.id = "bag";
      this.visavisBag_mc.id = "visavisBag";
      this.doLater("init");
      lol.core.SceneShifter.locationScreen.centerChar();
   }
   function init()
   {
      this.master = lol.core.Master.getInstance();
      this.bank = this.master.gamer.bank;
      this.bank.addEventListener("close",this,this.bankClose);
      var _loc2_ = this.master.gamer.attributes.gold;
      this.increaseBank_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.increaseBank);
      this.addGold_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.addGold);
      this.sortMask = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_MASK_BANK);
      this.bag_mc.sortMask = this.sortMask;
      this.visavisBag_mc.sortMask = this.sortMask;
      this.bag_mc.alignEnabled = true;
      this.visavisBag_mc.alignEnabled = true;
      this.bag_mc.priceEnabled = false;
      this.visavisBag_mc.priceEnabled = false;
      this.visavisBag_mc.showPriseInGold = false;
      this.bag_mc.addEventListener("changeMask",this,this.changeMaskBag);
      this.visavisBag_mc.addEventListener("changeMask",this,this.changeMaskBag);
      this.filterPan.addEventListener("changeMask",this);
      this.filterPan.init(this.sortMask);
      this.dropTarget = this.bank;
      this.master.gamer.equipment.addEventListener("addItem",this);
      this.master.gamer.equipment.addEventListener("removeItem",this);
      this.bank.addEventListener("addItem",this);
      this.bank.addEventListener("removeItem",this);
      this.bank.addEventListener("updWeight",this);
      this.bank.addEventListener(lol.gpui.DDEvents.TRANSFER_ERROR,this,this.moveItemError);
      this.bank.addEventListener(lol.gpui.DDEvents.TRANSFER_SUCCESS,this,this.moveItemSuccess);
      this.bank.addEventListener("separate",this,this.separateAck);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.bag_mc.addEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.addEventListener("removeItem",this,this.bagRemoveItem);
      this.bag_mc.addEventListener("attaching",this,this.bagAttaching);
      this.visavisBag_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.visavisBag_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.visavisBag_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.visavisBag_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.visavisBag_mc.addEventListener("addItem",this,this.bagAddItem);
      this.visavisBag_mc.addEventListener("removeItem",this,this.bagRemoveItem);
      this.visavisBag_mc.addEventListener("attaching",this,this.visavisAttaching);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.visavisBag_mc.bagPan.setSize(185,300);
      this.bag_mc.bagPan.setSize(185,300);
      this.listIconPan.addEventListener("changeView",this);
      this.typeOfList = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.TYPE_OF_LIST_BANK);
      this.listIconPan.init(this.typeOfList);
      this.bag_mc.typeOfList = this.typeOfList;
      this.visavisBag_mc.typeOfList = this.typeOfList;
      this.updWeight();
      this.initObjects();
      lol.core.SceneShifter.hotKeyManager.addFilter("cancel");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
   }
   function bankClose()
   {
      this.close();
   }
   function close()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function kill()
   {
      this.bank.removeEventListener("close",this,this.bankClose);
      this.increaseBank_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.increaseBank);
      this.addGold_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.addGold);
      this.bag_mc.removeEventListener("changeMask",this,this.changeMaskBag);
      this.filterPan.removeEventListener("changeMask",this);
      this.master.gamer.equipment.removeEventListener("addItem",this);
      this.master.gamer.equipment.removeEventListener("removeItem",this);
      this.bank.removeEventListener("addItem",this);
      this.bank.removeEventListener("removeItem",this);
      this.bank.removeEventListener("updWeight",this);
      this.bank.removeEventListener(lol.gpui.DDEvents.TRANSFER_ERROR,this,this.moveItemError);
      this.bank.removeEventListener(lol.gpui.DDEvents.TRANSFER_SUCCESS,this,this.moveItemSuccess);
      this.bank.removeEventListener("separate",this,this.separateAck);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.bag_mc.removeEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.removeEventListener("removeItem",this,this.bagRemoveItem);
      this.bag_mc.removeEventListener("attaching",this,this.bagAttaching);
      this.visavisBag_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.visavisBag_mc.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.visavisBag_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.visavisBag_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.visavisBag_mc.removeEventListener("addItem",this,this.bagAddItem);
      this.visavisBag_mc.removeEventListener("removeItem",this,this.bagRemoveItem);
      this.visavisBag_mc.removeEventListener("attaching",this,this.visavisAttaching);
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.listIconPan.removeEventListener("changeView",this);
      lol.core.SceneShifter.closeWindow("annotation","all");
      this.bank.close();
      lol.core.SceneShifter.hotKeyManager.removeFilter("cancel");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      super.kill();
   }
   function increaseBank()
   {
      var _loc2_ = this.master.gamer.attributes.gold;
      var _loc3_;
      if(_loc2_ >= 1)
      {
         this.bank.increaseBank();
      }
      else
      {
         _loc3_ = lol.core.SceneShifter.openNewWindow("alert");
         _loc3_.content.label = "У вас недостаточно денег";
      }
   }
   function visavisAttaching(obj)
   {
      var _loc2_ = obj.proc;
      this.ab1._xscale = _loc2_;
   }
   function bagAttaching(obj)
   {
      var _loc2_ = obj.proc;
      this.ab0._xscale = _loc2_;
   }
   function initObjects()
   {
      this.initBag(this.bank.bag);
      this.initBag(this.bank.visavisBag);
   }
   function clearObjects()
   {
      this.clearBag(this.bank.bag);
      this.clearBag(this.bank.visavisBag);
      this.bag_mc.firstAttaching = true;
      this.visavisBag_mc.firstAttaching = true;
   }
   function changeView(obj)
   {
      if(!this.bag_mc.attaching && !this.visavisBag_mc.attaching)
      {
         lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.TYPE_OF_LIST_BANK,obj.typeOfList);
         this.clearObjects();
         this.typeOfList = obj.typeOfList;
         this.bag_mc.linkageItem = obj.linkageItem;
         this.bag_mc.typeOfList = obj.typeOfList;
         this.visavisBag_mc.linkageItem = obj.linkageItem;
         this.visavisBag_mc.typeOfList = obj.typeOfList;
         this.doLater("initObjects");
      }
      else
      {
         this.listIconPan._typeOfList();
      }
   }
   function updWeight()
   {
      var _loc3_ = Number(this.bank.curWeight / 1000);
      var _loc2_ = Number(this.bank.maxWeight / 1000);
      this.info_txt.text = "Занято " + _loc3_ + " кг из " + _loc2_ + " кг";
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
      this.visavisBagInfo_txt.text = _loc2_;
      this.visavisBagInfo_txt.setTextFormat(_loc3_);
   }
   function changeMaskBag(obj)
   {
      this.sortMask = obj.sortMask;
      this.filterPan.sortMaskToggled(this.sortMask);
   }
   function changeMask(obj)
   {
      this.sortMask = obj.sortMask;
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SORT_MASK_BANK,this.sortMask);
      this.bag_mc.sortMask = this.sortMask;
      this.visavisBag_mc.sortMask = this.sortMask;
      this.bag_mc.resort();
      this.visavisBag_mc.resort();
      this.doLater("bagInfo",["bag"]);
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
         this.currDDOperation.setTo(0,this.visavisBag_mc);
         if(lol.core.objects.Heapable(this.currDDOperation.fromItem).heapSize > 1 && this.currDDOperation.fromItem instanceof lol.core.objects.Heapable)
         {
            _loc3_ = this.createExchangePan(this.currDDOperation.fromItem,"Сколько штук положить?");
            _loc3_.addEventListener("exchange",this,this.exchangeDropAck);
            _loc3_.addEventListener("close",this,this.exchangeCancel);
         }
         else
         {
            this.tryToSendTransferToServer();
         }
      }
      else
      {
         this.currDDOperation.setTo(0,this.bag_mc);
         this.tryToSendTransferToServer();
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
            if(!this.currDDOperation.group && lol.core.objects.Heapable(this.currDDOperation.firstItem).heapSize > 1 && this.currDDOperation.firstItem instanceof lol.core.objects.Heapable && this.currDDOperation.fromSlot == this.bag_mc && this.currDDOperation.toSlot == this.visavisBag_mc)
            {
               _loc2_ = this.createExchangePan(this.currDDOperation.fromItem,"Сколько штук положить?");
               _loc2_.addEventListener("exchange",this,this.exchangeDropAck);
               _loc2_.addEventListener("close",this,this.exchangeCancel);
            }
            else
            {
               this.tryToSendTransferToServer();
            }
         }
         else
         {
            this.moveItemError();
         }
      }
      delete this.onMouseMove;
   }
   function tryToSendTransferToServer()
   {
      var _loc7_;
      var _loc3_;
      var _loc2_;
      var _loc6_;
      var _loc8_;
      var _loc5_;
      if(this.currDDOperation.toSlot == this.bag_mc && this.currDDOperation.fromSlot == this.visavisBag_mc)
      {
         _loc7_ = this.weightPan.getMaxWeight();
         _loc3_ = this.weightPan.getCurWeight();
         _loc2_ = this.currDDOperation.fromItemMc_arr;
         if(_loc2_.length > 0)
         {
            for(var _loc4_ in _loc2_)
            {
               _loc3_ += _loc2_[_loc4_].item.getProp("_weight");
            }
         }
         else
         {
            _loc6_ = this.currDDOperation.fromItem._item;
            if(_loc6_)
            {
               _loc8_ = _loc6_.getProp("_weight");
               _loc3_ += _loc8_;
            }
         }
         if(_loc7_ < _loc3_)
         {
            _loc5_ = lol.core.SceneShifter.openNewWindow("query");
            _loc5_.content.label = "При взятии вещи вы будете перегружены. Взять?";
            _loc5_.content.addEventListener("click",this,this.checkAnswer);
         }
         else
         {
            this.sendTransferToServer();
         }
      }
      else
      {
         this.sendTransferToServer();
      }
   }
   function checkAnswer(obj)
   {
      obj.target.removeEventListener("click",this,this.checkAnswer);
      lol.core.SceneShifter.closeWindow("query");
      var _loc2_ = obj.success;
      if(_loc2_)
      {
         this.sendTransferToServer();
      }
      else
      {
         this.currDDOperation.failedOperation();
         delete this.currDDOperation;
      }
   }
   function sendTransferToServer()
   {
      var _loc3_ = this.currDDOperation.fromItemMc_arr;
      var _loc2_;
      if(_loc3_)
      {
         for(var _loc4_ in _loc3_)
         {
            _loc2_ = new lol.gpui.DDOperation();
            _loc2_.setFrom(_loc3_[_loc4_].item,this.currDDOperation.fromSlot,_loc3_[_loc4_]);
            _loc2_.setTo(this.currDDOperation.toItem,this.currDDOperation.toSlot,this.currDDOperation.toItemMc);
            this.ddOperation_arr.push(_loc2_);
            this.bank.transferItem(_loc2_.fromItem,_loc2_.fromSlot.id,_loc2_.toSlot.id,_loc2_.toItem);
         }
      }
      else
      {
         this.ddOperation_arr.push(this.currDDOperation);
         this.bank.transferItem(this.currDDOperation.fromItem,this.currDDOperation.fromSlot.id,this.currDDOperation.toSlot.id,this.currDDOperation.toItem);
      }
      delete this.currDDOperation;
   }
   function sendHeapToServer()
   {
      this.ddOperation_arr.push(this.currDDOperation);
      this.bank.separateHeap(lol.core.objects.Heapable(this.currDDOperation.fromItem),this.currDDOperation.heapNum);
      delete this.currDDOperation;
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
         this.tryToSendTransferToServer();
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
         if(_loc2_.fromSlot == this.bag_mc && _loc2_.toSlot == this.visavisBag_mc)
         {
            _loc2_.fromItemMc.blockItem();
            this.currDDOperation = new lol.gpui.DDOperation();
            this.currDDOperation.setFrom(_loc2_.fromItem,_loc2_.fromSlot,_loc2_.fromItemMc);
            this.currDDOperation.setTo(0,this.visavisBag_mc);
            this.tryToSendTransferToServer();
         }
      }
      else
      {
         _loc2_.failedOperation();
      }
   }
   function addGold()
   {
      var _loc2_ = lol.core.SceneShifter._ref.getProfileUrl();
      this.getURL(_loc2_,"_blank");
   }
}
