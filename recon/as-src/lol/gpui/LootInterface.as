class lol.gpui.LootInterface extends lol.gpui.StaffInterface
{
   var _xmouse;
   var _ymouse;
   var attachMovie;
   var bagInfo_txt;
   var bag_mc;
   var close_btn;
   var currDDOperation;
   var ddOperation_arr;
   var dispatchEvent;
   var doLater;
   var dragCont;
   var dragItemMc;
   var dragNdrop;
   var dropTarget;
   var exchangeMainSize;
   var exchangePanCost_num;
   var exchangePan_cost_mod;
   var exchangePan_showCostInGold;
   var filterPan;
   var heapSepItem;
   var listIconPan;
   var loot;
   var lootBag_mc;
   var lotBagInfo_txt;
   var onMouseMove;
   var priceEnabled;
   var separateItem;
   var slots;
   var sortMask;
   var takeAll_btn;
   var tempObj;
   var ddFlag = false;
   var exchangePanTitle = "";
   function LootInterface()
   {
      super();
      lol.gpui.StaffInterface.ssType = lol.gpui.StaffInterface.SS_LOOT;
      this.doLater("init");
      this.slots = new Array();
      this.slots.bag = this.bag_mc;
      this.slots.lootBag = this.lootBag_mc;
      this.bag_mc.id = "bag";
      this.lootBag_mc.id = "lootBag";
      this.bag_mc.alignEnabled = true;
      this.lootBag_mc.alignEnabled = false;
      lol.core.SceneShifter.locationScreen.centerChar();
   }
   function init()
   {
      var _loc2_ = lol.core.Master.getInstance();
      this.loot = _loc2_.gamer.loot;
      this.dropTarget = this.loot;
      this.sortMask = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_MASK_LOOT);
      this.bag_mc.sortMask = this.sortMask;
      this.lootBag_mc.sortMask = this.sortMask;
      this.filterPan.addEventListener("changeMask",this);
      this.bag_mc.addEventListener("changeMask",this,this.changeMaskBag);
      this.filterPan.init(this.sortMask);
      _loc2_.gamer.equipment.addEventListener("addItem",this);
      _loc2_.gamer.equipment.addEventListener("removeItem",this);
      this.loot.addEventListener("addItem",this);
      this.loot.addEventListener("removeItem",this);
      this.loot.addEventListener("separate",this,this.separateAck);
      this.loot.addEventListener(lol.gpui.DDEvents.TRANSFER_SUCCESS,this,this.moveItemSuccess);
      this.loot.addEventListener(lol.gpui.DDEvents.TRANSFER_ERROR,this,this.moveItemError);
      this.loot.addEventListener("closeWindow",this,this.close);
      this.lootBag_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.lootBag_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.lootBag_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.lootBag_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.lootBag_mc.addEventListener("addItem",this,this.bagAddItem);
      this.lootBag_mc.addEventListener("removeItem",this,this.bagRemoveItem);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.bag_mc.addEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.addEventListener("removeItem",this,this.bagRemoveItem);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.SEPARATE_HEAP,this,this.separateHeap);
      this.takeAll_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.transferAll);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      lol.core.SceneShifter.hotKeyManager.addFilter("loot");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.APPLY,this,this.close);
      this.lootBag_mc.bagPan.setSize(183,332);
      this.bag_mc.bagPan.setSize(185,332);
      this.listIconPan.addEventListener("changeView",this);
      this.typeOfList = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.TYPE_OF_LIST_LOOT);
      this.listIconPan.init(this.typeOfList);
      this.bag_mc.typeOfList = this.typeOfList;
      this.lootBag_mc.typeOfList = this.typeOfList;
      this.initObjects();
   }
   function transferAll()
   {
      this.loot.transferAll();
      this.loot.addEventListener("transferAll",this,this.transferAllOk);
   }
   function transferAllOk()
   {
      this.loot.removeEventListener("transferAll",this,this.transferAllOk);
      this.close();
   }
   function close()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function kill()
   {
      this.filterPan.kill();
      this.filterPan.removeEventListener("changeMask",this);
      this.listIconPan.kill();
      this.loot.removeEventListener("addItem",this);
      this.loot.removeEventListener("removeItem",this);
      this.loot.removeEventListener("separate",this,this.separateAck);
      this.loot.removeEventListener(lol.gpui.DDEvents.TRANSFER_SUCCESS,this,this.moveItemSuccess);
      this.loot.removeEventListener(lol.gpui.DDEvents.TRANSFER_ERROR,this,this.moveItemError);
      this.loot.removeEventListener("closeWindow",this,this.close);
      this.lootBag_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.lootBag_mc.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.lootBag_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.lootBag_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      lol.core.SceneShifter.hotKeyManager.removeFilter("loot");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.APPLY,this,this.close);
      this.filterPan.removeEventListener("changeMask",this);
      this.bag_mc.removeEventListener("changeMask",this,this.changeMaskBag);
      this.lootBag_mc.removeEventListener("changeMask",this,this.changeMaskBag);
      this.takeAll_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.transferAll);
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      var _loc3_ = lol.core.Master.getInstance();
      _loc3_.gamer.equipment.removeEventListener("addItem",this);
      _loc3_.gamer.equipment.removeEventListener("removeItem",this);
      lol.core.SceneShifter.closeWindow("annotation","all");
      super.kill();
   }
   function bagAddItem(obj)
   {
      this.doLater("bagInfo",[obj.id]);
   }
   function bagRemoveItem(obj)
   {
      this.doLater("bagInfo",[obj.id]);
   }
   function bagInfo(bag)
   {
      var _loc2_ = new TextFormat();
      _loc2_.bold = true;
      var _loc3_;
      if(bag == "bag")
      {
         _loc3_ = this.bag_mc.sortList.length;
         this.bagInfo_txt.text = _loc3_;
         this.bagInfo_txt.setTextFormat(_loc2_);
      }
      else if(bag == "lootBag")
      {
         _loc3_ = this.lootBag_mc.sortList.length;
         this.lotBagInfo_txt.text = _loc3_;
         this.lotBagInfo_txt.setTextFormat(_loc2_);
      }
   }
   function changeMaskBag(obj)
   {
      this.sortMask = obj.sortMask;
      this.filterPan.sortMaskToggled(this.sortMask);
   }
   function changeMask(obj)
   {
      this.sortMask = obj.sortMask;
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SORT_MASK_LOOT,this.sortMask);
      this.bag_mc.sortMask = this.sortMask;
      this.lootBag_mc.sortMask = this.sortMask;
      this.bag_mc.resort();
      this.lootBag_mc.resort();
      this.doLater("bagInfo",["bag"]);
   }
   function initObjects()
   {
      this.initBag(this.loot.bag);
      this.initBag(this.loot.lootBag);
   }
   function clearObjects()
   {
      this.clearBag(this.loot.bag);
      this.clearBag(this.loot.lootBag);
   }
   function changeView(obj)
   {
      if(!this.bag_mc.attaching && !this.lootBag_mc.attaching)
      {
         lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.TYPE_OF_LIST_LOOT,obj.typeOfList);
         this.clearObjects();
         this.typeOfList = obj.typeOfList;
         this.bag_mc.linkageItem = obj.linkageItem;
         this.bag_mc.typeOfList = obj.typeOfList;
         this.lootBag_mc.linkageItem = obj.linkageItem;
         this.lootBag_mc.typeOfList = obj.typeOfList;
         this.doLater("initObjects");
      }
      else
      {
         this.listIconPan._typeOfList();
      }
   }
   function dragging()
   {
      super.dragging();
      this.bag_mc.startDragAndScroll();
      this.lootBag_mc.startDragAndScroll();
   }
   function _mouseUp(obj)
   {
      super._mouseUp(obj);
      this.bag_mc.stopDragAndScroll();
      this.lootBag_mc.stopDragAndScroll();
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
         this.currDDOperation.setTo(0,this.lootBag_mc);
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
            if(!this.currDDOperation.group && lol.core.objects.Heapable(this.currDDOperation.fromItem).heapSize > 1 && this.currDDOperation.fromItem instanceof lol.core.objects.Heapable && this.currDDOperation.fromSlot == this.bag_mc && this.currDDOperation.toSlot == this.lootBag_mc)
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
      var _loc2_;
      if(_loc3_)
      {
         for(var _loc4_ in _loc3_)
         {
            _loc2_ = new lol.gpui.DDOperation();
            _loc2_.setFrom(_loc3_[_loc4_].item,this.currDDOperation.fromSlot,_loc3_[_loc4_]);
            _loc2_.setTo(this.currDDOperation.toItem,this.currDDOperation.toSlot,this.currDDOperation.toItemMc);
            this.ddOperation_arr.push(_loc2_);
            this.loot.transferItem(_loc2_.fromItem,_loc2_.fromSlot.id,_loc2_.toSlot.id,_loc2_.toItem);
         }
      }
      else
      {
         this.ddOperation_arr.push(this.currDDOperation);
         this.loot.transferItem(this.currDDOperation.fromItem,this.currDDOperation.fromSlot.id,this.currDDOperation.toSlot.id,this.currDDOperation.toItem);
      }
      delete this.currDDOperation;
   }
   function sendHeapToServer()
   {
      this.ddOperation_arr.push(this.currDDOperation);
      this.loot.separateHeap(lol.core.objects.Heapable(this.currDDOperation.fromItem),this.currDDOperation.heapNum);
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
      this.currDDOperation.fromItemMc.unblockItem();
      delete this.currDDOperation;
   }
   function separateHeap(obj)
   {
      if(!this.ddOperation_arr)
      {
         this.ddOperation_arr = new Array();
      }
      var _loc3_ = obj.item_mc;
      var _loc2_ = _loc3_.item;
      var _loc4_;
      if(_loc2_ instanceof lol.core.objects.Heapable && lol.core.objects.Heapable(_loc2_).heapSize > 1)
      {
         this.separateItem = lol.core.objects.Heapable(_loc2_);
         _loc4_ = this.createExchangePan(_loc2_,"Сколько отделить?");
         _loc4_.addEventListener("exchange",this,this.exchangeAck);
         _loc4_.addEventListener("close",this,this.exchangeCancel);
         this.currDDOperation = new lol.gpui.DDOperation();
         this.currDDOperation.setFrom(_loc2_,obj.target,_loc3_);
      }
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
   function exchangeAck(obj)
   {
      obj.target.removeEventListener("close",this,this.exchangeCancel);
      obj.target.removeEventListener("exchange",this,this.exchangeAck);
      lol.core.SceneShifter.closeWindow("exchange");
      this.currDDOperation.heapNum = obj.right;
      this.sendHeapToServer();
      delete this.separateItem;
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
      delete this.separateItem;
   }
   function exchangeCancel(obj)
   {
      obj.target.removeEventListener("close",this,this.exchangeCancel);
      obj.target.removeEventListener("exchange",this,this.exchangeAck);
      lol.core.SceneShifter.closeWindow("exchange");
      this.moveItemError();
      delete this.separateItem;
      delete this.currDDOperation;
   }
   function separateAck(obj)
   {
      var _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      if(obj.res == 0)
      {
         _loc2_.successOperation();
         if(_loc2_.fromSlot == this.bag_mc && _loc2_.toSlot == this.lootBag_mc)
         {
            _loc2_.fromItemMc.blockItem();
            this.currDDOperation = new lol.gpui.DDOperation();
            this.currDDOperation.setFrom(_loc2_.fromItem,_loc2_.fromSlot,_loc2_.fromItemMc);
            this.currDDOperation.setTo(0,this.lootBag_mc);
            this.sendTransferToServer();
         }
      }
      else
      {
         _loc2_.failedOperation();
      }
   }
   function startHandSeparate(obj)
   {
      this.exchangePanTitle = "Как разделить?";
      this.tempObj = obj;
      this.onMouseMove = this._startHandSeparate;
   }
   function _startHandSeparate()
   {
      delete this.onMouseMove;
      var _loc2_ = this.proposeSeparate(this.tempObj.item);
      _loc2_.addEventListener("exchange",this,this.handSeparate);
      _loc2_.addEventListener("close",this,this.handSeparateCancel);
   }
   function dragSeparate(obj)
   {
      if(obj.left != 0)
      {
         super.dragSeparate(obj);
      }
      else
      {
         obj.target.removeEventListener("close",this,this.dragSeparateCancel);
         obj.target.removeEventListener("exchange",this,this.dragSeparate);
         lol.core.SceneShifter.closeWindow("exchange");
         this.__drop();
         obj.target.removeEventListener("separate",this,this.dragSeparateAck);
         this.dropEnabled = true;
         delete this.dragCont.onMouseMove;
         this.dragCont.kill();
         this.dragCont.removeMovieClip();
         this.dragON = false;
         this.dragCont = null;
         this.heapSepItem = null;
         this.dropEnabled = true;
         delete this.dragNdrop;
      }
   }
   function dragSeparateCancel(obj)
   {
      this.bag_mc.addItem(this.heapSepItem);
      super.dragSeparateCancel(obj);
      delete this.dragCont.onMouseMove;
   }
   function checkSeparate()
   {
      if(this.dragNdrop.what.length == 1 && this.dragNdrop.what[0].item instanceof lol.core.objects.Heapable && this.dragNdrop.from.id == "bag" && this.dragNdrop.where.id == "lootBag" && this.dragNdrop.where.id != undefined)
      {
         return true;
      }
      return false;
   }
}
