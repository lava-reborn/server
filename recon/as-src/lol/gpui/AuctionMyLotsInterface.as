class lol.gpui.AuctionMyLotsInterface extends lol.gpui.StaffInterface
{
   var _xmouse;
   var _ymouse;
   var ab0;
   var attachMovie;
   var auction;
   var auctionPan;
   var bagInfo_txt;
   var bag_mc;
   var buyoutA_txt;
   var buyoutG_txt;
   var cancel_btn;
   var clearBag;
   var close_btn;
   var cost_mod;
   var createLot_btn;
   var curTime_btn;
   var currDDOperation;
   var currSort_btn;
   var ddOperation_arr;
   var dispatchEvent;
   var doLater;
   var dragItemMc;
   var dropEnabled;
   var equipment;
   var exchangeMainSize;
   var exchangePanCost_num;
   var exchangePan_cost_mod;
   var exchangePan_showCostInGold;
   var filterPan;
   var gamer;
   var info_txt;
   var initBag;
   var itemArr;
   var listIconPan;
   var lotSlot;
   var master;
   var moneyPan_afro;
   var moneyPan_gold;
   var onMouseMove;
   var priceEnabled;
   var rateA_txt;
   var rateG_txt;
   var searchObj;
   var selectItem;
   var sell_btn;
   var showItemRepairMod;
   var slots;
   var sortByCost_btn;
   var sortByCount_btn;
   var sortByMaster_btn;
   var sortByName_btn;
   var sortByTime_btn;
   var sortMask;
   var tf;
   var time12_btn;
   var time24_btn;
   var time48_btn;
   var typeOfList;
   var itemCount = 0;
   var ddFlag = false;
   var prev_rateG = "";
   var prev_rateA = "";
   function AuctionMyLotsInterface()
   {
      super();
      this.doLater("init");
      this.master = lol.core.Master.getInstance();
      this.gamer = this.master.gamer;
      this.auction = this.gamer.auction;
      this.equipment = this.gamer.equipment;
      this.slots = new Array();
      this.slots.bag = this.bag_mc;
      this.slots.lot = this.lotSlot;
      this.bag_mc.id = "bag";
      this.lotSlot.id = "lot";
      this.tf = new TextFormat();
      this.tf.bold = true;
   }
   function init()
   {
      this.moneyPan_afro.type = "afro";
      this.moneyPan_afro.setPlayer(this.gamer);
      this.moneyPan_gold.type = "gold";
      this.moneyPan_gold.setPlayer(this.gamer);
      this.auctionPan.fillContent();
      this.auctionPan.setSize(428,180);
      this.sortMask = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_MASK_AUCTION);
      this.filterPan.addEventListener("changeMask",this,this.changeMask);
      this.filterPan.init(this.sortMask);
      this.listIconPan.addEventListener("changeView",this,this.changeView);
      this.typeOfList = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.TYPE_OF_LIST_AUCTION);
      this.listIconPan.init(this.typeOfList);
      this.bag_mc.typeOfList = this.typeOfList;
      this.bag_mc.alignEnabled = true;
      this.bag_mc.bagPan.setSize(185,337);
      this.bag_mc.dragEnabled = true;
      this.bag_mc.selectGroupAvailable = false;
      this.bag_mc.sortMask = this.sortMask;
      this.bag_mc.addEventListener("changeMask",this,this.changeMaskBag);
      this.bag_mc.addEventListener("attaching",this,this.bagAttaching);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.bag_mc.addEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.addEventListener("removeItem",this,this.bagRemoveItem);
      this.lotSlot.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.lotSlot.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.lotSlot.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.lotSlot.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.lotSlot.addEventListener("addItem",this,this.checkCreateLot);
      this.doLater("initObjects");
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.sell_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sell);
      this.cancel_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.cancel);
      this.cancel_btn.enabled = false;
      this.sell_btn.enabled = false;
      this.auction.typeOfAuc = 1;
      this.auction.addEventListener(lol.core.player.Auction.ADD_LOT,this,this.addLot);
      this.auction.addEventListener(lol.core.player.Auction.SEARCH_RESULT,this,this.searchResult);
      this.auction.addEventListener(lol.core.player.Auction.TOO_OFTEN,this,this.tooOften);
      this.equipment.addEventListener("addItem",this);
      this.equipment.addEventListener("removeItem",this);
      this.equipment.addEventListener(lol.gpui.DDEvents.TRANSFER_ERROR,this,this.moveItemError);
      this.equipment.addEventListener(lol.gpui.DDEvents.TRANSFER_SUCCESS,this,this.moveItemSuccess);
      this.equipment.addEventListener("separate",this,this.separateAck);
      this.createLot_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.createLot);
      this.sortByName_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByCount_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByTime_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByMaster_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByCost_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.time12_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setTime);
      this.time24_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setTime);
      this.time48_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setTime);
      this.time24_btn.toggled = true;
      this.curTime_btn = this.time24_btn;
      this.rateA_txt.restrict = "0-9";
      this.buyoutA_txt.restrict = "0-9";
      this.rateG_txt.restrict = "0-9.";
      this.buyoutG_txt.restrict = "0-9.";
      this.rateA_txt.onChanged = mx.utils.Delegate.create(this,this.check_rateA_txt);
      this.buyoutA_txt.onChanged = mx.utils.Delegate.create(this,this.check_buyoutA_txt);
      this.rateG_txt.onChanged = mx.utils.Delegate.create(this,this.check_rateG_txt);
      this.buyoutG_txt.onChanged = mx.utils.Delegate.create(this,this.check_buyoutG_txt);
      this.info_txt.html = true;
      this.info_txt.text = "";
      this.rateA_txt.tabIndex = 0;
      this.buyoutA_txt.tabIndex = 1;
      this.rateG_txt.tabIndex = 2;
      this.buyoutG_txt.tabIndex = 3;
      this.currSort_btn = this.sortByName_btn;
      this.currSort_btn.setFrame(lol.gpui.controls.SortButton.SORT_UP_FRAME);
      this.updateLotList();
      this.checkCreateLot();
      lol.core.SceneShifter.locationScreen.centerChar();
      lol.core.SceneShifter.hotKeyManager.addFilter("auction");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.ESC,this,this.close);
   }
   function kill()
   {
      this.filterPan.kill();
      this.filterPan.removeEventListener("changeMask",this,this.changeMask);
      this.listIconPan.kill();
      this.listIconPan.removeEventListener("changeView",this,this.changeView);
      this.clearAuctionPan();
      this.bag_mc.removeEventListener("attaching",this,this.bagAttaching);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.bag_mc.removeEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.removeEventListener("removeItem",this,this.bagRemoveItem);
      this.lotSlot.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.lotSlot.removeEventListener("addItem",this,this.checkCreateLot);
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.sell_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sell);
      this.cancel_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.cancel);
      this.auction.removeEventListener(lol.core.player.Auction.ADD_LOT,this,this.addLot);
      this.auction.removeEventListener(lol.core.player.Auction.SEARCH_RESULT,this,this.searchResult);
      this.auction.removeEventListener(lol.core.player.Auction.TOO_OFTEN,this,this.tooOften);
      this.equipment.removeEventListener("addItem",this);
      this.equipment.removeEventListener("removeItem",this);
      this.equipment.removeEventListener(lol.gpui.DDEvents.TRANSFER_ERROR,this,this.moveItemError);
      this.equipment.removeEventListener(lol.gpui.DDEvents.TRANSFER_SUCCESS,this,this.moveItemSuccess);
      this.equipment.removeEventListener("separate",this,this.separateAck);
      this.createLot_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.createLot);
      this.sortByName_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByCount_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByTime_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByMaster_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.sortByCost_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortOn);
      this.time12_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setTime);
      this.time24_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setTime);
      this.time48_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setTime);
      lol.core.SceneShifter.hotKeyManager.removeFilter("auction");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.ESC,this,this.close);
      this.moneyPan_afro.kill();
      this.moneyPan_gold.kill();
      this.bag_mc.kill();
      super.kill();
   }
   function close()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function initObjects()
   {
      this.initBag(this.equipment.bag);
   }
   function clearObjects()
   {
      this.clearBag(this.equipment.bag);
   }
   function bagAttaching(obj)
   {
      var _loc2_ = obj.proc;
      this.ab0._xscale = _loc2_;
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
         this.currDDOperation.setTo(this.lotSlot.item,this.lotSlot);
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
            if(!this.currDDOperation.group && lol.core.objects.Heapable(this.currDDOperation.fromItem).heapSize > 1 && this.currDDOperation.fromItem instanceof lol.core.objects.Heapable && this.currDDOperation.fromSlot == this.bag_mc && this.currDDOperation.toSlot == this.lotSlot)
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
      var _loc2_ = this.currDDOperation.fromItemMc_arr;
      var _loc3_;
      if(this.currDDOperation.fromSlot == this.bag_mc && this.currDDOperation.toSlot == this.lotSlot)
      {
         if(this.checkDragItem())
         {
            if(this.currDDOperation.toItem)
            {
               this.currDDOperation.fromSlot.addItem(this.currDDOperation.toItem);
            }
            this.currDDOperation.fromSlot.removeItem(this.currDDOperation.fromItem);
            this.currDDOperation.toSlot.addItem(this.currDDOperation.fromItem);
         }
         else
         {
            this.currDDOperation.failedOperation();
         }
      }
      else if(this.currDDOperation.fromSlot == this.bag_mc && this.currDDOperation.toSlot == this.bag_mc)
      {
         this.ddOperation_arr.push(this.currDDOperation);
         this.equipment.transferItem(this.currDDOperation.fromItem,this.currDDOperation.fromSlot.id,this.currDDOperation.toSlot.id,this.currDDOperation.toItem);
      }
      else if(this.currDDOperation.fromSlot == this.lotSlot && this.currDDOperation.toSlot == this.bag_mc)
      {
         this.currDDOperation.fromSlot.removeItem(this.currDDOperation.fromItem);
         this.currDDOperation.toSlot.addItem(this.currDDOperation.fromItem);
         this.clearLotFields();
      }
      delete this.currDDOperation;
   }
   function sendHeapToServer()
   {
      this.ddOperation_arr.push(this.currDDOperation);
      this.equipment.separateHeap(lol.core.objects.Heapable(this.currDDOperation.fromItem),this.currDDOperation.heapNum);
      delete this.currDDOperation;
   }
   function checkDragItem()
   {
      var _loc2_ = this.currDDOperation.fromItem;
      var _loc3_ = true;
      var _loc4_;
      if(_loc2_ instanceof lol.core.objects.Breakable)
      {
         _loc4_ = lol.core.objects.Breakable(_loc2_).getCurQuality();
         if(_loc4_ < 0.15)
         {
            _loc3_ = false;
            this.createAlert("Нельзя выложить предмет поломанный более чем на 85%");
         }
      }
      if(!_loc2_.getProp("exchang"))
      {
         _loc3_ = false;
         this.createAlert("Этот предмет нельзя выставить на аукцион, так как он непередаваемый");
      }
      if(_loc2_.getProp("cost") == 0)
      {
         _loc3_ = false;
         this.createAlert("Этот предмет нельзя выставить на аукцион, потому что у него нет фиксированной цены в афро");
      }
      return _loc3_;
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
         if(_loc2_.fromSlot == this.bag_mc && _loc2_.toSlot == this.lotSlot)
         {
            _loc2_.fromItemMc.blockItem();
            this.currDDOperation = new lol.gpui.DDOperation();
            this.currDDOperation.setFrom(_loc2_.fromItem,_loc2_.fromSlot,_loc2_.fromItemMc);
            this.currDDOperation.setTo(this.lotSlot.item,this.lotSlot);
            this.sendTransferToServer();
         }
      }
      else
      {
         _loc2_.failedOperation();
      }
   }
   function tooOften(obj)
   {
      if(obj.value)
      {
         this.sortByName_btn.enabled = true;
         this.sortByCount_btn.enabled = true;
         this.sortByTime_btn.enabled = true;
         this.sortByMaster_btn.enabled = true;
         this.sortByCost_btn.enabled = true;
      }
      else
      {
         this.sortByName_btn.enabled = false;
         this.sortByCount_btn.enabled = false;
         this.sortByTime_btn.enabled = false;
         this.sortByMaster_btn.enabled = false;
         this.sortByCost_btn.enabled = false;
      }
   }
   function addLot(obj)
   {
      var _loc6_ = lol.core.objects.Lot(obj.lot);
      var _loc3_ = this.auctionPan.content;
      var _loc5_ = _loc3_.getNextHighestDepth();
      var _loc4_;
      if(this.itemCount % 2 == 0)
      {
         _loc4_ = "auctionItem";
      }
      else
      {
         _loc4_ = "auctionItem_2";
      }
      var _loc2_ = lol.gpui.AuctionItem(_loc3_.attachMovie(_loc4_,"auctionItem" + this.itemCount,_loc5_));
      _loc2_.addEventListener(lol.gpui.AuctionItem.SELECT_ITEM,this,this.select);
      _loc2_.initByLot(_loc6_,true);
      _loc2_._y = this.itemCount * 29;
      this.itemCount = this.itemCount + 1;
      this.itemArr.push(_loc2_);
      this.auctionPan.chekSize();
      this.auctionPan.setPosition(0,0);
   }
   function searchResult(obj)
   {
      if(obj.count == 0)
      {
         this.createInfo("У вас нет товаров на продажу");
      }
      else
      {
         this.clearAuctionPan();
      }
   }
   function updateLotList()
   {
      this.searchObj = this.getSearchObject();
      this.auction.search(this.searchObj);
   }
   function sell(obj)
   {
      var _loc2_ = lol.gpui.dialogue.GPUIDialogue(lol.core.SceneShifter.openNewWindow("query").content);
      if(this.selectItem.lot.rateACost)
      {
         _loc2_.label = "Продать предмет\r&lt;" + this.selectItem.lot.name + "&gt;\r за " + this.selectItem.lot.rateACost + " Афро?";
      }
      else if(this.selectItem.lot.rateGCost)
      {
         _loc2_.label = "Продать предмет\r&lt;" + this.selectItem.lot.name + "&gt;\r за " + this.selectItem.lot.rateGCost / 100 + " унций золота?";
      }
      _loc2_.addEventListener("click",this,this._sell);
   }
   function _sell(obj)
   {
      obj.target.removeEventListener("click",this,this._sell);
      lol.core.SceneShifter.closeWindow("query");
      if(obj.success)
      {
         this.auction.addEventListener(lol.core.player.Auction.SELL_LOT_RESULT,this,this.sellLotAck);
         this.auction.sellsLot(this.selectItem.lot.item.id);
         this.sell_btn.enabled = false;
         this.cancel_btn.enabled = false;
      }
   }
   function sellLotAck(obj)
   {
      this.auction.removeEventListener(lol.core.player.Auction.SELL_LOT_RESULT,this,this.sellLotAck);
      if(obj.res == 0)
      {
         this.createAlert("Товар продан");
      }
      else if(obj.res == 40)
      {
         this.createAlert("Лот не найден");
      }
      else
      {
         this.createAlert("У вас недостаточно денег");
      }
   }
   function cancel(obj)
   {
      var _loc2_ = lol.gpui.dialogue.GPUIDialogue(lol.core.SceneShifter.openNewWindow("query").content);
      _loc2_.label = "Отменить аукцион предмета\r&lt;" + this.selectItem.lot.name + "&gt;?";
      _loc2_.addEventListener("click",this,this._cancel);
   }
   function _cancel(obj)
   {
      obj.target.removeEventListener("click",this,this._cancel);
      lol.core.SceneShifter.closeWindow("query");
      if(obj.success)
      {
         this.auction.addEventListener(lol.core.player.Auction.CANCEL_LOT_RESULT,this,this.cancelLotAck);
         this.auction.cancelLot(this.selectItem.lot.item.id);
         this.sell_btn.enabled = false;
         this.cancel_btn.enabled = false;
      }
   }
   function cancelLotAck(obj)
   {
      this.auction.removeEventListener(lol.core.player.Auction.CANCEL_LOT_RESULT,this,this.cancelLotAck);
      if(obj.res == 0)
      {
         this.info_txt.htmlText = "<font color=\'#3fb83f\'>Аукцион отменен</font>";
         this.info_txt.setTextFormat(this.tf);
      }
      else if(obj.res == 40)
      {
         this.createAlert("Лот не найден");
      }
      else
      {
         this.createAlert("Невозможно отменить аукцион");
      }
   }
   function select(obj)
   {
      if(lol.gpui.AuctionItem(obj.target) != this.selectItem)
      {
         this.selectItem.unselect();
         this.selectItem = lol.gpui.AuctionItem(obj.target);
         this.sell_btn.enabled = this.selectItem.lot.bidder;
         this.cancel_btn.enabled = true;
      }
   }
   function sortOn(obj)
   {
      var _loc2_ = lol.gpui.controls.SortButton(obj.target);
      if(this.currSort_btn != _loc2_)
      {
         this.currSort_btn.setFrame(lol.gpui.controls.SortButton.STATIC_FRAME);
         this.currSort_btn = _loc2_;
      }
      if(this.itemCount)
      {
         this.updateLotList();
      }
   }
   function clearAuctionPan()
   {
      for(var _loc2_ in this.itemArr)
      {
         lol.gpui.AuctionItem(this.itemArr[_loc2_]).removeEventListener(lol.gpui.AuctionItem.SELECT_ITEM,this,this.select);
         lol.gpui.AuctionItem(this.itemArr[_loc2_]).kill();
         lol.gpui.AuctionItem(this.itemArr[_loc2_]).removeMovieClip();
      }
      this.cancel_btn.enabled = false;
      this.sell_btn.enabled = false;
      this.itemArr = new Array();
      this.auctionPan.fillContent();
      this.itemCount = 0;
      delete this.selectItem;
   }
   function createLot()
   {
      this.auction.addEventListener(lol.core.player.Auction.CREATE_LOT_RESULT,this,this.createLotAck);
      var _loc2_ = new lol.core.objects.Lot();
      switch(this.curTime_btn)
      {
         case this.time12_btn:
            _loc2_.time = 24;
            break;
         case this.time24_btn:
            _loc2_.time = 72;
            break;
         case this.time48_btn:
            _loc2_.time = 168;
      }
      if(this.rateA_txt.text || this.buyoutA_txt.text)
      {
         _loc2_.rateACost = !this.rateA_txt.text ? 0 : Number(this.rateA_txt.text);
         _loc2_.buyoutACost = !this.buyoutA_txt.text ? 0 : Number(this.buyoutA_txt.text);
      }
      else if(this.rateG_txt.text || this.buyoutG_txt.text)
      {
         _loc2_.rateGCost = !this.rateG_txt.text ? 0 : Math.floor(Number(this.rateG_txt.text) * 100);
         _loc2_.buyoutGCost = !this.buyoutG_txt.text ? 0 : Math.floor(Number(this.buyoutG_txt.text) * 100);
      }
      _loc2_.item = this.lotSlot.item;
      this.auction.createLot(_loc2_);
   }
   function clearLotFields()
   {
      this.lotSlot.removeItem();
      this.curTime_btn.toggled = false;
      this.curTime_btn = this.time24_btn;
      this.curTime_btn.toggled = true;
      this.rateA_txt.text = "";
      this.rateG_txt.text = "";
      this.buyoutA_txt.text = "";
      this.buyoutG_txt.text = "";
      this.createLot_btn.enabled = false;
      this.info_txt.htmlText = "";
      this.info_txt.setTextFormat(this.tf);
   }
   function createLotAck(obj)
   {
      this.auction.removeEventListener(lol.core.player.Auction.CREATE_LOT_RESULT,this,this.createLotAck);
      if(obj.res == 0)
      {
         this.clearLotFields();
         this.info_txt.htmlText = "<font color=\'#3fb83f\'>Товар выставлен на аукцион</font>";
         this.info_txt.setTextFormat(this.tf);
      }
      else if(obj.res == 9)
      {
         this.createAlert("У вас недостаточно денег");
      }
   }
   function setTime(obj)
   {
      if(obj.target != this.curTime_btn)
      {
         this.curTime_btn.toggled = false;
         this.curTime_btn = lol.gpui.controls.ToggleButton(obj.target);
      }
      else
      {
         this.curTime_btn.toggled = true;
      }
      this.checkComission();
   }
   function _checkCreateLot()
   {
      if(this.lotSlot.item_mc && (this.rateA_txt.text || this.rateG_txt.text))
      {
         if(!this.createLot_btn.enabled)
         {
            this.createLot_btn.enabled = true;
         }
      }
      else if(this.createLot_btn.enabled)
      {
         this.createLot_btn.enabled = false;
      }
      this.checkCreateLot();
   }
   function check_rateA_txt()
   {
      this.rateG_txt.text = "";
      this.buyoutG_txt.text = "";
      this.checkCreateLot();
   }
   function check_rateG_txt()
   {
      this.rateA_txt.text = "";
      this.buyoutA_txt.text = "";
      var _loc2_;
      if(this.rateG_txt.text == "")
      {
         this.prev_rateG = "";
      }
      else
      {
         _loc2_ = Number(this.rateG_txt.text);
         if(_loc2_ || _loc2_ == 0)
         {
            this.prev_rateG = _loc2_;
         }
         else
         {
            this.rateG_txt.text = this.prev_rateG;
         }
      }
      this.checkCreateLot();
   }
   function check_buyoutA_txt()
   {
      this.rateG_txt.text = "";
      this.buyoutG_txt.text = "";
      this.checkCreateLot();
   }
   function check_buyoutG_txt()
   {
      this.rateA_txt.text = "";
      this.buyoutA_txt.text = "";
      var _loc2_;
      if(this.rateA_txt.text == "")
      {
         this.prev_rateA = "";
      }
      else
      {
         _loc2_ = Number(this.rateA_txt.text);
         if(_loc2_ || _loc2_ == 0)
         {
            this.prev_rateA = _loc2_;
         }
         else
         {
            this.rateA_txt.text = this.prev_rateA;
         }
      }
      this.checkCreateLot();
   }
   function checkCreateLot()
   {
      var _loc2_ = Number(this.rateA_txt.text);
      var _loc3_ = Number(this.rateG_txt.text);
      var _loc6_ = Number(this.buyoutA_txt.text);
      var _loc4_ = Number(this.buyoutG_txt.text);
      var _loc5_ = "";
      if(this.lotSlot.item_mc)
      {
         if(_loc2_ && _loc6_ < _loc2_ && _loc6_ != 0 || _loc3_ && _loc4_ < _loc3_ && _loc4_ != 0)
         {
            _loc5_ = "<font color=\'#b83f3f\'>Цена выкупа не может быть ниже начальной ставки</font>";
            this.createLot_btn.enabled = false;
         }
         else if(!_loc2_ && !_loc3_ && !_loc6_ && !_loc4_)
         {
            this.createLot_btn.enabled = false;
         }
         else
         {
            if(!(!_loc2_ || _loc2_ <= 0))
            {
               this.createLot_btn.enabled = true;
               this.checkComission();
               return undefined;
            }
            _loc5_ = "<font color=\'#b83f3f\'>Начальная ставка должна быть больше нуля</font>";
            this.createLot_btn.enabled = false;
         }
         this.info_txt.htmlText = _loc5_;
         this.info_txt.setTextFormat(this.tf);
      }
      else
      {
         this.createLot_btn.enabled = false;
      }
   }
   function checkComission()
   {
      var _loc2_ = "";
      var _loc3_ = this.lotSlot.item.getProp("size");
      _loc3_ = !_loc3_ ? 1 : _loc3_;
      if(this.rateA_txt.text || this.buyoutA_txt.text)
      {
         switch(this.curTime_btn)
         {
            case this.time12_btn:
               _loc2_ = "\rКомиссия: " + Math.ceil(Number(this.lotSlot.item.getProp("cost")) * 0.05 * _loc3_) + " А";
               break;
            case this.time24_btn:
               _loc2_ = "\rКомиссия: " + Math.ceil(Number(this.lotSlot.item.getProp("cost")) * 0.07 * _loc3_) + " А";
               break;
            case this.time48_btn:
               _loc2_ = "\rКомиссия: " + Math.ceil(Number(this.lotSlot.item.getProp("cost")) * 0.09 * _loc3_) + " А";
         }
      }
      else if(this.rateG_txt.text || this.buyoutG_txt.text)
      {
         switch(this.curTime_btn)
         {
            case this.time12_btn:
               _loc2_ = "Комиссия составит 2% от цены продажи лота, но не менее 0.5 унций золота";
               break;
            case this.time24_btn:
               _loc2_ = "Комиссия составит 3% от цены продажи лота, но не менее 0.75 унций золота";
               break;
            case this.time48_btn:
               _loc2_ = "Комиссия составит 4% от цены продажи лота, но не менее 1 унции золота";
         }
      }
      this.info_txt.htmlText = _loc2_;
      this.info_txt.setTextFormat(this.tf);
   }
   function changeView(obj)
   {
      if(!this.bag_mc.attaching)
      {
         lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.TYPE_OF_LIST_AUCTION,obj.typeOfList);
         this.clearObjects();
         this.typeOfList = obj.typeOfList;
         this.bag_mc.linkageItem = obj.linkageItem;
         this.bag_mc.typeOfList = obj.typeOfList;
         this.doLater("initObjects");
      }
      else
      {
         this.listIconPan._typeOfList();
      }
   }
   function bagInfo()
   {
      var _loc2_ = this.bag_mc.sortList.length;
      this.bagInfo_txt.text = _loc2_;
      this.bagInfo_txt.setTextFormat(this.tf);
   }
   function changeMaskBag(obj)
   {
      this.sortMask = obj.sortMask;
      this.filterPan.sortMaskToggled(this.sortMask);
   }
   function changeMask(obj)
   {
      this.sortMask = obj.sortMask;
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SORT_MASK_AUCTION,this.sortMask);
      this.bag_mc.sortMask = this.sortMask;
      this.bag_mc.resort();
      this.doLater("bagInfo");
   }
   function bagAddItem(obj)
   {
      this.doLater("bagInfo");
   }
   function bagRemoveItem(obj)
   {
      this.doLater("bagInfo");
   }
   function createInfo(str)
   {
      var _loc2_ = this.auctionPan.fillContent("auc_info_mc");
      _loc2_.info_txt.text = str;
      var _loc3_ = new TextFormat();
      _loc3_.bold = true;
      _loc2_.info_txt.setTextFormat(_loc3_);
      this.auctionPan.chekSize();
   }
   function createAlert(str)
   {
      var _loc1_ = lol.gpui.dialogue.GPUIAlert(lol.core.SceneShifter.openNewWindow("alert").content);
      _loc1_.label = str;
   }
   function getSearchObject()
   {
      var _loc2_ = new Object();
      _loc2_.name = "";
      _loc2_.category = 101;
      _loc2_.type = -1;
      _loc2_.min_level = 0;
      _loc2_.max_level = 0;
      _loc2_.min_aCost = 0;
      _loc2_.max_aCost = 0;
      _loc2_.min_gCost = 0;
      _loc2_.max_gCost = 0;
      _loc2_.sortBy = this.getSortBy().sort;
      _loc2_.sortByMode = this.getSortBy().s_mode;
      return _loc2_;
   }
   function getSortBy()
   {
      var _loc2_ = new Object();
      switch(this.currSort_btn)
      {
         case this.sortByName_btn:
            _loc2_.sort = 0;
            break;
         case this.sortByCount_btn:
            _loc2_.sort = 1;
            break;
         case this.sortByTime_btn:
            _loc2_.sort = 2;
            break;
         case this.sortByMaster_btn:
            _loc2_.sort = 3;
            break;
         case this.sortByCost_btn:
            _loc2_.sort = 4;
      }
      if(this.currSort_btn.currentState == lol.gpui.controls.SortButton.SORT_DOWN_FRAME)
      {
         _loc2_.s_mode = 0;
      }
      else
      {
         _loc2_.s_mode = 1;
      }
      return _loc2_;
   }
}
