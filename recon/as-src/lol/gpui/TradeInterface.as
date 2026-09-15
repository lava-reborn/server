class lol.gpui.TradeInterface extends lol.gpui.StaffInterface
{
   var _xmouse;
   var _ymouse;
   var ab0;
   var ab1;
   var addGold_btn;
   var afroChangedNum;
   var attachMovie;
   var bagInfo_txt;
   var bag_mc;
   var close_btn;
   var currDDOperation;
   var ddOperation_arr;
   var dispatchEvent;
   var doLater;
   var dragItemMc;
   var dropTarget;
   var filterPan;
   var getURL;
   var goldChangedNum;
   var listIconPan;
   var master;
   var moneyPan;
   var onMouseMove;
   var prevAfroSumm;
   var prevGoldSumm;
   var separateItem;
   var showPrise;
   var slots;
   var sortMask;
   var trade;
   var tradeBagInfo_txt;
   var trader;
   var visavisBag_mc;
   var weightPan;
   var priceEnabled = true;
   var ddFlag = false;
   function TradeInterface()
   {
      super();
      lol.gpui.StaffInterface.ssType = lol.gpui.StaffInterface.SS_TRADE;
      this.bag_mc.alignEnabled = true;
      this.visavisBag_mc.alignEnabled = false;
      this.doLater("init");
      this.slots = new Array();
      this.slots.bag = this.bag_mc;
      this.slots.visavisBag = this.visavisBag_mc;
      this.bag_mc.id = "bag";
      this.visavisBag_mc.id = "visavisBag";
      lol.core.SceneShifter.locationScreen.centerChar();
   }
   function tradeClose()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function close()
   {
      this.trade.close();
      this.dispatchEvent({type:"closeWindow"});
   }
   function init()
   {
      this.master = lol.core.Master.getInstance();
      this.trade = this.master.gamer.trade;
      this.trade.addEventListener("close",this,this.tradeClose);
      this.trade.addEventListener(lol.gpui.DDEvents.TRANSFER_ERROR,this,this.moveItemError);
      this.trade.addEventListener(lol.gpui.DDEvents.TRANSFER_SUCCESS,this,this.moveItemSuccess);
      this.trade.addEventListener("separate",this,this.separateAck);
      this.sortMask = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_MASK_TRADE);
      this.bag_mc.sortMask = this.sortMask;
      this.visavisBag_mc.sortMask = this.sortMask;
      this.bag_mc.priceEnabled = true;
      this.visavisBag_mc.showHeapCount = false;
      this.visavisBag_mc.priceEnabled = true;
      this.visavisBag_mc.showPriseInGold = true;
      this.visavisBag_mc.selectGroupAvailable = false;
      this.bag_mc.addEventListener("changeMask",this,this.changeMaskBag);
      this.filterPan.addEventListener("changeMask",this);
      this.filterPan.init(this.sortMask);
      this.master.gamer.addEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
      this.dropTarget = this.trade;
      this.master.gamer.equipment.addEventListener("addItem",this);
      this.master.gamer.equipment.addEventListener("removeItem",this);
      this.trade.addEventListener("addItem",this);
      this.trade.addEventListener("removeItem",this);
      this.trade.addEventListener("sell",this);
      this.trade.addEventListener("buy",this);
      this.bag_mc.addEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.addEventListener("removeItem",this,this.bagRemoveItem);
      this.bag_mc.addEventListener("attaching",this,this.bagAttaching);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.visavisBag_mc.addEventListener("addItem",this,this.bagAddItem);
      this.visavisBag_mc.addEventListener("removeItem",this,this.bagRemoveItem);
      this.visavisBag_mc.addEventListener("attaching",this,this.visavisAttaching);
      this.visavisBag_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.visavisBag_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.visavisBag_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.addGold_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goToUserPage);
      this.visavisBag_mc.bagPan.setSize(185,337);
      this.bag_mc.bagPan.setSize(185,337);
      this.listIconPan.addEventListener("changeView",this);
      this.typeOfList = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.TYPE_OF_LIST_TRADE);
      this.listIconPan.init(this.typeOfList);
      this.bag_mc.typeOfList = this.typeOfList;
      this.visavisBag_mc.typeOfList = this.typeOfList;
      this.doLater("initObjects");
      this.userInfoUpdate();
      this.trader = lol.core.player.Trader(this.master.getPlayer(this.trade.visavisID));
      this.trader.loadSellList();
      this.trader.loadBGSellList();
      this.cost_mod = this.trader.smod;
      this.bag_mc.cost_mod = this.cost_mod;
      this.bag_mc.showItemSellMod = true;
      this.visavisBag_mc.cost_mod = this.trader.pmod;
      this.showPrise = true;
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
      this.master.gamer.equipment.removeEventListener("addItem",this);
      this.master.gamer.equipment.removeEventListener("removeItem",this);
      this.trade.removeEventListener("addItem",this);
      this.trade.removeEventListener("removeItem",this);
      this.trade.removeEventListener("close",this,this.tradeClose);
      this.trade.removeEventListener("sell",this);
      this.trade.removeEventListener("buy",this);
      this.bag_mc.removeEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.removeEventListener("removeItem",this,this.bagRemoveItem);
      this.bag_mc.removeEventListener("attaching",this,this.bagAttaching);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.SEPARATE_HEAP,this,this.separateHeap);
      this.visavisBag_mc.removeEventListener("addItem",this,this.bagAddItem);
      this.visavisBag_mc.removeEventListener("removeItem",this,this.bagRemoveItem);
      this.visavisBag_mc.removeEventListener("attaching",this,this.visavisAttaching);
      this.visavisBag_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.visavisBag_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.visavisBag_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.addGold_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goToUserPage);
      lol.core.SceneShifter.closeWindow("annotation","all");
      super.kill();
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
      this.initBag(this.trade.bag);
      this.initBag(this.trade.visavisBag);
   }
   function clearObjects()
   {
      this.clearBag(this.trade.bag);
      this.clearBag(this.trade.visavisBag);
      this.bag_mc.firstAttaching = true;
      this.visavisBag_mc.firstAttaching = true;
   }
   function changeView(obj)
   {
      if(!this.bag_mc.attaching && !this.visavisBag_mc.attaching)
      {
         lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.TYPE_OF_LIST_TRADE,obj.typeOfList);
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
   function userInfoUpdate(obj)
   {
      var _loc2_ = lol.core.Master.getInstance();
      this.showMoney(_loc2_.gamer.attributes.afro);
      this.afroChangedNum = Math.abs(this.prevAfroSumm - _loc2_.gamer.attributes.afro);
      this.goldChangedNum = Math.abs(this.prevGoldSumm - _loc2_.gamer.attributes.gold);
      this.prevAfroSumm = _loc2_.gamer.attributes.afro;
      this.prevGoldSumm = _loc2_.gamer.attributes.gold;
   }
   function showMoney(afro)
   {
      this.moneyPan.value = afro;
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
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SORT_MASK_TRADE,this.sortMask);
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
         if(this.currDDOperation.toSlot == this.visavisBag_mc && this.currDDOperation.fromSlot == this.bag_mc)
         {
            this.currDDOperation.setTo(0,this.visavisBag_mc);
            if(!this.currDDOperation.group && this.currDDOperation.fromItem instanceof lol.core.objects.Heapable && lol.core.objects.Heapable(this.currDDOperation.fromItem).heapSize > 1)
            {
               this.separateItem = lol.core.objects.Heapable(this.currDDOperation.fromItem);
               _loc2_ = this.createExchangePan(this.separateItem,"Сколько штук продать?",this.trader.smod,false,true);
               _loc2_.addEventListener("exchange",this,this.exchangeAck);
               _loc2_.addEventListener("close",this,this.exchangeCancel);
            }
            else
            {
               this.askTradeItem();
            }
         }
         else if(this.currDDOperation.toSlot == this.bag_mc && this.currDDOperation.fromSlot == this.visavisBag_mc)
         {
            if(this.currDDOperation.fromItem.rootID == lol.core.objects.Item.AMMO)
            {
               this.separateItem = lol.core.objects.Heapable(this.currDDOperation.fromItem);
               _loc2_ = this.createExchangePan(this.currDDOperation.fromItem,"Сколько штук купить?",this.trader.pmod,true,false);
               _loc2_.addEventListener("exchange",this,this.exchangeAck);
               _loc2_.addEventListener("close",this,this.exchangeCancel);
            }
            else
            {
               this.tryToSendTransferToServer();
            }
         }
         else
         {
            this.tryToSendTransferToServer();
         }
      }
      delete this.onMouseMove;
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
         if(_loc2_.item instanceof lol.core.objects.Heapable && lol.core.objects.Heapable(this.currDDOperation.fromItem).heapSize > 1)
         {
            this.separateItem = lol.core.objects.Heapable(this.currDDOperation.fromItem);
            _loc3_ = this.createExchangePan(this.separateItem,"Сколько штук продать?",this.trader.smod,false,true);
            _loc3_.addEventListener("exchange",this,this.exchangeAck);
            _loc3_.addEventListener("close",this,this.exchangeCancel);
         }
         else
         {
            this.askTradeItem();
         }
      }
      else
      {
         this.currDDOperation.setTo(0,this.bag_mc);
         if(_loc2_.item.rootID == lol.core.objects.Item.AMMO)
         {
            this.separateItem = lol.core.objects.Heapable(this.currDDOperation.fromItem);
            _loc3_ = this.createExchangePan(this.currDDOperation.fromItem,"Сколько штук купить?",this.trader.pmod,true,false);
            _loc3_.addEventListener("exchange",this,this.exchangeAck);
            _loc3_.addEventListener("close",this,this.exchangeCancel);
         }
         else
         {
            this.tryToSendTransferToServer();
         }
      }
   }
   function separateHeap(obj)
   {
      if(!this.ddOperation_arr)
      {
         this.ddOperation_arr = new Array();
      }
      var _loc3_ = obj.item_mc;
      var _loc2_ = lol.core.objects.Item(_loc3_.item);
      var _loc4_;
      if(_loc2_ instanceof lol.core.objects.Heapable && lol.core.objects.Heapable(_loc2_).heapSize > 1)
      {
         _loc4_ = this.createExchangePan(_loc2_,"Сколько отделить?");
         _loc4_.addEventListener("exchange",this,this.separateExchangeAck);
         _loc4_.addEventListener("close",this,this.exchangeCancel);
         this.currDDOperation = new lol.gpui.DDOperation();
         this.currDDOperation.setFrom(_loc2_,obj.target,_loc3_);
      }
   }
   function separateExchangeAck(obj)
   {
      obj.target.removeEventListener("close",this,this.separateExchangeAck);
      obj.target.removeEventListener("exchange",this,this.dragSeparate);
      lol.core.SceneShifter.closeWindow("exchange");
      this.currDDOperation.heapNum = obj.right;
      this.sendHeapToServer();
      delete this.separateItem;
   }
   function createExchangePan(_item, title_str, mode, show_g_cost, sell_bool)
   {
      var _loc5_ = lol.core.objects.Heapable(_item);
      var _loc7_ = lol.core.SceneShifter.openNewWindow("exchange");
      var _loc2_ = lol.gpui.ExchangePan(_loc7_.content);
      _loc2_.label = title_str;
      _loc2_.sell_bool = sell_bool;
      var _loc6_;
      var _loc3_;
      if(mode)
      {
         _loc6_ = _item.getProp("cost");
         _loc3_ = _item.getProp("g_cost");
         if(show_g_cost && _loc3_)
         {
            _loc2_.cost_num = _loc3_;
            _loc2_.showCostInGold = show_g_cost;
         }
         else
         {
            _loc2_.cost_num = _loc6_;
         }
      }
      _loc2_.cost_mod = mode;
      _loc2_.maxValue = !_loc5_.heapSize ? _item.getProp("size") : _loc5_.heapSize;
      this.dropEnabled = false;
      return _loc2_;
   }
   function exchangeAck(obj)
   {
      obj.target.removeEventListener("close",this,this.dragSeparateCancel);
      obj.target.removeEventListener("exchange",this,this.dragSeparate);
      lol.core.SceneShifter.closeWindow("exchange");
      this.currDDOperation.heapNum = obj.right;
      this.tryToSendTransferToServer();
      delete this.separateItem;
   }
   function exchangeCancel(obj)
   {
      obj.target.removeEventListener("close",this,this.dragSeparateCancel);
      obj.target.removeEventListener("exchange",this,this.dragSeparate);
      lol.core.SceneShifter.closeWindow("exchange");
      this.moveItemError();
      delete this.separateItem;
      delete this.currDDOperation;
   }
   function sendTransferToServer()
   {
      var _loc3_ = this.currDDOperation.fromItemMc_arr;
      var _loc4_;
      var _loc2_;
      if(_loc3_.length > 1)
      {
         for(var _loc5_ in _loc3_)
         {
            _loc2_ = new lol.gpui.DDOperation();
            _loc2_.setFrom(_loc3_[_loc5_].item,this.currDDOperation.fromSlot,_loc3_[_loc5_]);
            _loc2_.setTo(this.currDDOperation.toItem,this.currDDOperation.toSlot,this.currDDOperation.toItemMc);
            if(this.checkSellItem(_loc2_.fromItem) && this.currDDOperation.toSlot == this.visavisBag_mc && this.currDDOperation.fromSlot == this.bag_mc)
            {
               _loc4_ = this.checkSellItem(_loc2_.fromItem);
               _loc2_.failedOperation();
            }
            else
            {
               this.ddOperation_arr.push(_loc2_);
               this.trade.transferItem(_loc2_.fromItem,_loc2_.fromSlot.id,_loc2_.toSlot.id,_loc2_.toItem);
            }
         }
      }
      else if(this.checkSellItem(this.currDDOperation.fromItem) && this.currDDOperation.toSlot == this.visavisBag_mc && this.currDDOperation.fromSlot == this.bag_mc)
      {
         _loc4_ = this.checkSellItem(this.currDDOperation.fromItem);
         this.currDDOperation.failedOperation();
      }
      else
      {
         this.ddOperation_arr.push(this.currDDOperation);
         this.trade.transferItem(this.currDDOperation.fromItem,this.currDDOperation.fromSlot.id,this.currDDOperation.toSlot.id,this.currDDOperation.toItem,this.currDDOperation.heapNum);
      }
      var _loc6_;
      if(_loc4_)
      {
         _loc6_ = lol.core.SceneShifter.openNewWindow("alert");
         _loc6_.content.label = _loc4_;
      }
      delete this.currDDOperation;
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
   function askTradeItem()
   {
      var _loc3_ = false;
      var _loc2_ = this.currDDOperation.fromItemMc_arr;
      var _loc5_;
      var _loc7_;
      if(_loc2_ != undefined && _loc2_.length >= 1)
      {
         for(var _loc4_ in _loc2_)
         {
            _loc5_ = _loc2_[_loc4_].item.getProp("g_cost");
            if(_loc5_ != undefined && !isNaN(_loc5_) && _loc5_ > 0)
            {
               _loc3_ = true;
            }
         }
      }
      else
      {
         _loc7_ = this.currDDOperation.fromItem;
         if(_loc7_)
         {
            _loc5_ = _loc7_.getProp("g_cost");
            if(_loc5_ != undefined && !isNaN(_loc5_) && _loc5_ > 0)
            {
               _loc3_ = true;
            }
         }
      }
      var _loc6_;
      if(_loc3_)
      {
         _loc6_ = lol.core.SceneShifter.openNewWindow("queryTradeItem");
         _loc6_.content.label = "ВНИМАНИЕ! Восстановление проданного предмета невозможно. Для подтверждения введите слово \"ПРОДАТЬ\"";
      }
      else
      {
         this.tryToSendTransferToServer();
      }
      _loc6_.content.addEventListener("click",this,this.askTradeItemAck);
   }
   function askTradeItemAck(obj)
   {
      lol.core.SceneShifter.closeWindow("query");
      lol.core.SceneShifter.closeWindow("queryTradeItem");
      obj.target.removeEventListener("click",this,this.askTradeItemAck);
      if(obj.success)
      {
         this.tryToSendTransferToServer();
      }
      else
      {
         this.currDDOperation.failedOperation();
         delete this.currDDOperation;
      }
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
         if(_loc2_.length > 1)
         {
            for(var _loc4_ in _loc2_)
            {
               _loc3_ += _loc2_[_loc4_].item._item.getProp("_weight");
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
            _loc5_.content.label = "При покупке вы будете перегружены. Купить?";
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
   function sendHeapToServer()
   {
      this.ddOperation_arr.push(this.currDDOperation);
      this.trade.separateHeap(lol.core.objects.Heapable(this.currDDOperation.fromItem),this.currDDOperation.heapNum);
      delete this.currDDOperation;
   }
   function checkSellItem(_item)
   {
      var _loc1_;
      var _loc3_ = _item.getProp("__break");
      var _loc2_ = _item.getProp("cost");
      if(_loc2_ == 0)
      {
         _loc1_ = "Вы не можете продать некоторые предметы";
      }
      else if(_loc3_ == 0)
      {
         _loc1_ = "Вы не можете продать полностью сломанный предмет";
      }
      else if(_item.rootID == lol.core.objects.Item.TROPHY)
      {
         _loc1_ = "Вы не можете продать трофеи";
      }
      return _loc1_;
   }
   function moveItemSuccess()
   {
      var _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      _loc2_.successOperation();
   }
   function moveItemError()
   {
      var _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      var _loc3_;
      if(_loc2_.fromSlot == this.visavisBag_mc && _loc2_.toSlot == this.bag_mc)
      {
         _loc3_ = lol.core.SceneShifter.openNewWindow("alert");
         _loc3_.content.label = "У вас недостаточно средств";
      }
      _loc2_.failedOperation();
      this.currDDOperation.fromItemMc.unblockItem();
      this.currDDOperation.failedOperation();
      delete this.currDDOperation;
   }
   function separateAck(obj)
   {
      var _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      _loc2_.successOperation();
   }
   function buy(obj)
   {
      var _loc2_ = obj.item;
      var _loc3_ = _loc2_.getProp("size") == undefined ? 1 : _loc2_.getProp("size");
      lol.services.GameEvents.addEvent(lol.services.GameEvents.BUY,{itemname:_loc2_,value:_loc3_,value2:this.getOperationCost()});
   }
   function sell(obj)
   {
      var _loc2_ = obj.item;
      var _loc3_ = _loc2_.getProp("size") == undefined ? 1 : _loc2_.getProp("size");
      lol.services.GameEvents.addEvent(lol.services.GameEvents.SELL,{itemname:_loc2_,value:_loc3_,value2:this.getOperationCost()});
   }
   function getOperationCost()
   {
      var _loc2_ = this.afroChangedNum != 0 ? this.afroChangedNum + " афро" : Number(this.goldChangedNum / 100) + " унций золота";
      this.goldChangedNum = 0;
      this.afroChangedNum = 0;
      return _loc2_;
   }
   function goToUserPage()
   {
      var _loc2_ = lol.core.SceneShifter._ref.getProfileUrl();
      this.getURL(_loc2_,"_blank");
   }
}
