class lol.gpui.RepairInterface extends lol.gpui.StaffInterface
{
   var _alpha;
   var _parent;
   var _xmouse;
   var _ymouse;
   var addItem;
   var afroPan;
   var attachMovie;
   var bagInfo_txt;
   var bag_mc;
   var close_btn;
   var cost_mod;
   var currDDOperation;
   var ddOperation_arr;
   var dispatchEvent;
   var doLater;
   var dragCont;
   var dragEnabled;
   var dragItemMc;
   var dragNdrop;
   var dragON;
   var dropTarget;
   var filterPan;
   var goldPan;
   var item_mc;
   var listIconPan;
   var master;
   var onEnterFrame;
   var onMouseMove;
   var removeItem;
   var repairAfroCost_txt;
   var repairAllByAfro_btn;
   var repairAllByGold_btn;
   var repairAllCostAfro_txt;
   var repairAllCostGold_txt;
   var repairByAfro_btn;
   var repairByGold_btn;
   var repairGoldCost_txt;
   var repair_slot;
   var restoreGoldCost_txt;
   var restoreGold_btn;
   var showItemRepairMod;
   var slots;
   var sortMask;
   var trade;
   var typeOfList;
   var priceEnabled = true;
   var ddFlag = false;
   function RepairInterface()
   {
      super();
      lol.gpui.StaffInterface.ssType = lol.gpui.StaffInterface.SS_REPAIR;
      this.showItemRepairMod = true;
      this.doLater("init");
      this.slots = new Array();
      this.slots.bag = this.bag_mc;
      this.slots.repairSlot = this.repair_slot;
      this.bag_mc.id = "bag";
      this.repair_slot.id = "repairSlot";
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
      this.master.gamer.addEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
      this.showMoney(this.master.gamer.attributes);
      this.dropTarget = this.trade;
      this.master.gamer.equipment.addEventListener("addItem",this);
      this.master.gamer.equipment.addEventListener("removeItem",this);
      this.trade.addEventListener("addItem",this);
      this.trade.addEventListener("removeItem",this);
      this.bag_mc.addEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.addEventListener("removeItem",this,this.bagRemoveItem);
      this.bag_mc.alignEnabled = true;
      this.bag_mc.priceEnabled = true;
      this.bag_mc.selectGroupAvailable = false;
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.repair_slot.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.repair_slot.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.repair_slot.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.repair_slot.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.bag_mc.bagPan.setSize(185,332);
      this.listIconPan.addEventListener("changeView",this);
      this.typeOfList = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.TYPE_OF_LIST_REPAIR);
      this.typeOfList = this.typeOfList != undefined ? this.typeOfList : "icon";
      this.listIconPan.init(this.typeOfList);
      this.bag_mc.typeOfList = this.typeOfList;
      this.sortMask = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_MASK_TRADE);
      this.bag_mc.sortMask = this.sortMask;
      this.bag_mc.addEventListener("changeMask",this,this.changeMaskBag);
      this.filterPan.addEventListener("changeMask",this);
      this.filterPan.init(this.sortMask);
      this.repairByAfro_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.repairItem);
      this.repairByGold_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.repairByGoldItem);
      this.restoreGold_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.restoreGoldItem);
      this.repairAllByAfro_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.repairAllItemsByAfro);
      this.repairAllByGold_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.repairAllItemsByGold);
      this.repairByAfro_btn.enabled = false;
      this.repairByGold_btn.enabled = false;
      this.restoreGold_btn.enabled = false;
      var _loc2_ = lol.core.player.Trader(this.master.getPlayer(this.trade.visavisID));
      this.cost_mod = _loc2_.rmod;
      this.bag_mc.cost_mod = this.cost_mod;
      this.bag_mc.showItemRepairMod = true;
      lol.core.SceneShifter.hotKeyManager.addFilter("cancel");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      this.initObjects();
   }
   function kill()
   {
      this.filterPan.kill();
      this.filterPan.removeEventListener("changeMask",this);
      this.repairByAfro_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.repairItem);
      this.repairByGold_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.repairByGoldItem);
      this.restoreGold_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.restoreGoldItem);
      this.repairAllByAfro_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.repairAllItemsByAfro);
      this.repairAllByGold_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.repairAllItemsByGold);
      this.listIconPan.kill();
      this.listIconPan.removeEventListener("changeView",this);
      this.master.gamer.removeEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
      this.master.gamer.equipment.removeEventListener("addItem",this);
      this.master.gamer.equipment.removeEventListener("removeItem",this);
      this.trade.removeEventListener("addItem",this);
      this.trade.removeEventListener("removeItem",this);
      this.trade.removeEventListener("close",this,this.tradeClose);
      this.bag_mc.removeEventListener("_mouseDown",this);
      this.bag_mc.removeEventListener("_mouseUp",this);
      this.bag_mc.removeEventListener("shiftMouseDown",this);
      this.bag_mc.removeEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.removeEventListener("removeItem",this,this.bagRemoveItem);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.repair_slot.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.repair_slot.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.repair_slot.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.repair_slot.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      lol.core.SceneShifter.closeWindow("annotation","all");
      lol.core.SceneShifter.hotKeyManager.removeFilter("cancel");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      super.kill();
   }
   function initObjects()
   {
      var _loc2_ = this.master.gamer.equipment.getBreakedItems();
      for(var _loc3_ in _loc2_)
      {
         this.bag_mc.addItem(_loc2_[_loc3_]);
      }
      this.repairAllCostAfro_txt.text = String(this.countAllRepairAfroCost());
      this.repairAllCostGold_txt.text = String(this.countAllRepairGoldCost());
   }
   function clearObjects()
   {
      this.bag_mc.removeAllItems();
   }
   function changeView(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.TYPE_OF_LIST_REPAIR,obj.typeOfList);
      this.clearObjects();
      this.typeOfList = obj.typeOfList;
      this.bag_mc.linkageItem = obj.linkageItem;
      this.bag_mc.typeOfList = obj.typeOfList;
      this.doLater("initObjects");
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
      this.bag_mc.resort();
      this.doLater("bagInfo",["bag"]);
   }
   function userInfoUpdate(obj)
   {
      var _loc2_ = lol.core.Master.getInstance();
      this.showMoney(_loc2_.gamer.attributes);
   }
   function showMoney(pers_attributes)
   {
      this.afroPan.type = "afro";
      this.afroPan.value = pers_attributes.afro;
      this.goldPan.type = "gold";
      this.goldPan.value = pers_attributes.gold;
   }
   function repairAllItemsByAfro()
   {
      var _loc4_ = lol.core.SceneShifter.openNewWindow("query");
      var _loc2_ = _loc4_.content;
      var _loc3_ = this.countAllRepairAfroCost();
      _loc2_.label = "Отремонтировать все\rсломанные предметы?\r<B>Стоимость: " + _loc3_ + " А</B>";
      _loc2_.addEventListener("click",this,this._repairAllItemByAfro);
   }
   function repairAllItemsByGold()
   {
      var _loc4_ = lol.core.SceneShifter.openNewWindow("query");
      var _loc2_ = _loc4_.content;
      var _loc3_ = this.countAllRepairGoldCost();
      _loc2_.label = "Отремонтировать все\rсломанные предметы?\r<B>Стоимость: " + _loc3_ + " G</B>";
      _loc2_.addEventListener("click",this,this._repairAllItemByGold);
   }
   function countAllRepairAfroCost()
   {
      var _loc9_ = 0;
      var _loc8_ = this.master.gamer.equipment.getBreakedItems();
      var _loc3_ = 0;
      var _loc2_;
      var _loc6_;
      var _loc5_;
      var _loc7_;
      var _loc4_;
      while(_loc3_ < _loc8_.length)
      {
         _loc2_ = _loc8_[_loc3_];
         _loc6_ = this.cost_mod;
         _loc5_ = _loc2_.getProp("repair_mod");
         if(_loc5_ != null)
         {
            _loc6_ *= _loc5_;
         }
         _loc7_ = 1 - lol.core.objects.Breakable(_loc2_).getCurQuality();
         _loc4_ = _loc2_.getProp("cost");
         if(_loc4_)
         {
            _loc9_ += Math.floor(_loc4_ * _loc6_ * _loc7_);
         }
         _loc3_ = _loc3_ + 1;
      }
      return _loc9_;
   }
   function calcGoldCostFromAfroCost(afro_cost)
   {
      var _loc1_ = Math.floor(afro_cost / lol.core.GConstatns.gold_repair_mod * 100) / 100;
      if(_loc1_ < 0.01)
      {
         _loc1_ = 0.01;
      }
      return _loc1_;
   }
   function countAllRepairGoldCost()
   {
      var _loc10_ = 0;
      var _loc9_ = this.master.gamer.equipment.getBreakedItems();
      var _loc3_ = 0;
      var _loc2_;
      var _loc5_;
      var _loc4_;
      var _loc7_;
      var _loc8_;
      var _loc6_;
      while(_loc3_ < _loc9_.length)
      {
         _loc2_ = _loc9_[_loc3_];
         _loc5_ = this.cost_mod;
         _loc4_ = _loc2_.getProp("repair_mod");
         if(_loc4_ != null)
         {
            _loc5_ *= _loc4_;
         }
         _loc7_ = 1 - lol.core.objects.Breakable(_loc2_).getCurQuality();
         _loc8_ = Math.floor(_loc2_.getProp("cost") * _loc5_ * _loc7_);
         _loc6_ = this.calcGoldCostFromAfroCost(_loc8_);
         if(_loc2_.getProp("cost"))
         {
            _loc10_ += _loc6_;
         }
         _loc3_ = _loc3_ + 1;
      }
      return _loc10_;
   }
   function _repairAllItemByAfro(obj)
   {
      obj.target.removeEventListener("click",this,this._repairAllItemByAfro);
      lol.core.SceneShifter.closeWindow("query");
      var _loc3_;
      var _loc2_;
      if(obj.success)
      {
         _loc3_ = this.master.gamer.equipment.getBreakedItems();
         for(var _loc4_ in _loc3_)
         {
            _loc2_ = _loc3_[_loc4_];
            this.dropTarget.repairItem(_loc2_);
            this.dropTarget.addEventListener("repAck",this,this.repAllAck);
         }
      }
   }
   function _repairAllItemByGold(obj)
   {
      obj.target.removeEventListener("click",this,this._repairAllItemByGold);
      lol.core.SceneShifter.closeWindow("query");
      var _loc3_;
      var _loc2_;
      if(obj.success)
      {
         _loc3_ = this.master.gamer.equipment.getBreakedItems();
         for(var _loc4_ in _loc3_)
         {
            _loc2_ = _loc3_[_loc4_];
            this.dropTarget.repairItem(_loc2_,true);
            this.dropTarget.addEventListener("repAck",this,this.repAllAck);
         }
      }
   }
   function repAllAck(obj)
   {
      var _loc2_ = this.bag_mc.itemList;
      if(_loc2_.length == 1)
      {
         this.dropTarget.removeEventListener("repAck",this,this.repAllAck);
      }
      var _loc4_;
      var _loc3_;
      if(obj.param.res == "0")
      {
         _loc4_ = _loc2_[0].item;
         this.bag_mc.removeItem(_loc4_);
         if(this.repair_slot.item_mc.item)
         {
            this.breakBar();
         }
      }
      else
      {
         _loc3_ = lol.core.SceneShifter.openNewWindow("alert");
         _loc3_.content.label = "Некоторые предметы не удалось отремонтировать";
         this.dropTarget.removeEventListener("repAck",this,this.repAllAck);
      }
   }
   function repairItem()
   {
      var _loc2_ = this.repair_slot.item_mc.item;
      if(_loc2_)
      {
         this.dropTarget.repairItem(_loc2_);
         this.trade.addEventListener("repAck",this,this.repAck);
      }
   }
   function repairByGoldItem()
   {
      var _loc2_ = this.repair_slot.item_mc.item;
      if(_loc2_)
      {
         this.dropTarget.repairItem(_loc2_,true);
         this.trade.addEventListener("repAck",this,this.repAck);
      }
   }
   function restoreGoldItem()
   {
      var _loc2_ = this.repair_slot.item_mc.item;
      if(_loc2_)
      {
         this.dropTarget.restoreItem(_loc2_);
         this.trade.addEventListener("repAck",this,this.repAck);
      }
   }
   function repAck(obj)
   {
      this.trade.removeEventListener("repAck",this,this.repAck);
      if(obj.param.res == "0")
      {
         this.breakBar();
      }
   }
   function breakBar()
   {
      this.repair_slot.onEnterFrame = function()
      {
         var _loc2_ = this.item_mc.breakBar;
         _loc2_.prevFrame();
         if(_loc2_._currentframe == 1)
         {
            delete this.onEnterFrame;
            this._parent.itemOut();
         }
      };
      this.repairAfroCost_txt.text = "";
      this.repairGoldCost_txt.text = "";
      this.restoreGoldCost_txt.text = "";
      this.repairByAfro_btn.enabled = false;
      this.repairByGold_btn.enabled = false;
      this.restoreGold_btn.enabled = false;
   }
   function itemOut()
   {
      var _loc4_ = this.repair_slot._width;
      var _loc3_ = this.repair_slot._height;
      var n = 1;
      this.repair_slot.onEnterFrame = function()
      {
         n *= 1.5;
         this._alpha = 100 - n;
         if(this._alpha < 0)
         {
            delete this.onEnterFrame;
            this._parent.removeItem({slot:this,item:this.item_mc.item});
            this._alpha = 100;
         }
      };
   }
   function startDragNDrop(obj)
   {
      if(!this.ddOperation_arr)
      {
         this.ddOperation_arr = new Array();
      }
      var _loc2_ = obj.item_mc;
      var _loc3_ = obj.target;
      _loc2_.blockItem();
      this.ddFlag = true;
      this.createDragItemMc(_loc2_.item);
      this.currDDOperation = new lol.gpui.DDOperation();
      this.currDDOperation.setFrom(_loc2_.__item,_loc3_,_loc2_);
   }
   function createDragItemMc(_item)
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
      this.dragItemMc.item = _item;
      this.dragItemMc.attachIcon(_item);
      this.draggingItem();
      this.onMouseMove = this.draggingItem;
   }
   function doubleClick(obj)
   {
      var _loc2_ = obj.item_mc;
      if(obj.target == this.bag_mc)
      {
         if(this.repair_slot.item_mc.item)
         {
            this.bag_mc.addItem(this.repair_slot.item_mc.item);
         }
         this.repair_slot.addItem(_loc2_.item);
         this.bag_mc.removeItem(_loc2_.item);
      }
      else
      {
         this.bag_mc.addItem(this.repair_slot.item_mc.item);
         this.repair_slot.removeItem(this.repair_slot.item_mc.item);
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
      var _loc3_;
      if(this.ddFlag)
      {
         _loc3_ = obj.target;
         this.currDDOperation.setTo(0,obj.target);
      }
   }
   function onMouseUp()
   {
      if(this.ddFlag)
      {
         this.ddFlag = false;
         this.dragItemMc.kill();
         this.dragItemMc.removeMovieClip();
         if(this.currDDOperation.fromSlot == this.bag_mc && this.currDDOperation.toSlot == this.repair_slot)
         {
            if(this.repair_slot.item_mc.item)
            {
               this.bag_mc.addItem(this.repair_slot.item_mc.item);
            }
            this.repair_slot.addItem(this.currDDOperation.fromItem);
            this.bag_mc.removeItem(this.currDDOperation.fromItem);
         }
         else if(this.currDDOperation.fromSlot == this.repair_slot && this.currDDOperation.toSlot == this.bag_mc)
         {
            this.bag_mc.addItem(this.currDDOperation.fromItem);
            this.repair_slot.removeItem(this.currDDOperation.fromItem);
         }
         else
         {
            this.currDDOperation.failedOperation();
            delete this.currDDOperation;
         }
      }
      delete this.onMouseMove;
   }
   function draggingItem()
   {
      this.dragItemMc._x = Math.round(this._xmouse - this.dragItemMc._width / 2);
      this.dragItemMc._y = Math.round(this._ymouse - this.dragItemMc._height / 2);
   }
   function repairCostCount()
   {
      var _loc3_ = this.repair_slot.item_mc.item;
      var _loc8_;
      var _loc5_;
      var _loc7_;
      var _loc2_;
      var _loc10_;
      var _loc6_;
      var _loc9_;
      var _loc4_;
      if(_loc3_)
      {
         _loc8_ = lol.core.objects.Breakable(_loc3_);
         _loc5_ = _loc8_.getCurQuality();
         _loc7_ = !_loc5_ ? this.cost_mod : this.cost_mod * (1 - _loc5_);
         _loc6_ = _loc3_.getProp("repair_mod");
         if(_loc6_ != null)
         {
            _loc2_ = Math.floor(_loc7_ * Number(_loc3_.getProp("cost")) * _loc6_);
         }
         else
         {
            _loc2_ = Math.floor(_loc7_ * Number(_loc3_.getProp("cost")));
         }
         _loc2_ = _loc2_ != 0 ? _loc2_ : 1;
         this.repairAfroCost_txt.text = _loc2_;
         _loc10_ = this.calcGoldCostFromAfroCost(_loc2_);
         this.repairByAfro_btn.enabled = true;
         this.repairByGold_btn.enabled = true;
         this.repairGoldCost_txt.text = _loc10_;
         _loc9_ = this.repair_slot.item_mc.item;
         _loc4_ = _loc9_.getProp("g_cost");
         if(_loc4_)
         {
            this.restoreGoldCost_txt.text = String(Math.round(_loc4_ * lol.core.GConstatns.gold_restore_price_mod) / 100);
            this.restoreGold_btn.enabled = true;
         }
         else
         {
            this.restoreGoldCost_txt.text = "";
            this.restoreGold_btn.enabled = false;
         }
      }
      else
      {
         this.repairAfroCost_txt.text = "0";
         this.repairGoldCost_txt.text = "0";
         this.restoreGoldCost_txt.text = "0";
         this.repairByAfro_btn.enabled = false;
         this.repairByGold_btn.enabled = false;
         this.restoreGold_btn.enabled = false;
      }
   }
   function onDoubleClick()
   {
      delete this.onMouseMove;
      var _loc3_;
      var _loc4_;
      var _loc9_;
      var _loc6_;
      var _loc8_;
      var _loc2_;
      var _loc10_;
      var _loc7_;
      var _loc5_;
      if(!this.dragON && this.dragNdrop.what && this.dragNdrop.where != this.repair_slot)
      {
         this.dragEnabled = false;
         _loc3_ = this.dragNdrop.what[0].item;
         this.removeItem({slot:this.bag_mc,item:_loc3_});
         _loc4_ = this.repair_slot.item_mc.item;
         if(_loc4_)
         {
            this.addItem({slot:this.bag_mc,item:_loc4_});
         }
         this.addItem({slot:this.repair_slot,item:_loc3_});
         this.dragNdrop = null;
         _loc9_ = lol.core.objects.Breakable(_loc3_);
         _loc6_ = _loc9_.getCurQuality();
         _loc8_ = !_loc6_ ? this.cost_mod : this.cost_mod * (1 - _loc6_);
         _loc7_ = _loc3_.getProp("repair_mod");
         if(_loc7_ != null)
         {
            _loc2_ = Math.floor(_loc8_ * Number(_loc3_.getProp("cost")) * _loc7_);
         }
         else
         {
            _loc2_ = Math.floor(_loc8_ * Number(_loc3_.getProp("cost")));
         }
         _loc2_ = _loc2_ != 0 ? _loc2_ : 1;
         this.repairAfroCost_txt.text = _loc2_;
         _loc10_ = this.calcGoldCostFromAfroCost(_loc2_);
         this.repairGoldCost_txt.text = _loc10_;
         this.repairByAfro_btn.enabled = true;
         _loc4_ = this.repair_slot.item_mc.item;
         _loc5_ = _loc4_.getProp("g_cost");
         if(_loc5_)
         {
            this.restoreGoldCost_txt.text = String(Math.round(_loc5_ * lol.core.GConstatns.gold_restore_price_mod) / 100);
            this.restoreGold_btn.enabled = true;
         }
         else
         {
            this.restoreGoldCost_txt.text = "";
            this.restoreGold_btn.enabled = false;
         }
      }
   }
   function drop()
   {
      var _loc5_;
      var _loc9_;
      var _loc6_;
      var _loc8_;
      var _loc2_;
      var _loc4_;
      var _loc7_;
      var _loc3_;
      if(this.dragON)
      {
         this.dragON = false;
         this.dragNdrop.from.pressOut();
         if(this.dragNdrop.where.id == "repairSlot")
         {
            _loc5_ = this.dragNdrop.where.item_mc.item;
            if(_loc5_)
            {
               this.addItem({slot:this.bag_mc,item:_loc5_});
            }
         }
         if(this.dragNdrop.where == undefined)
         {
            this.addItem({slot:this.dragNdrop.from,item:this.dragNdrop.what[0].item});
         }
         else
         {
            this.addItem({slot:this.dragNdrop.where,item:this.dragNdrop.what[0].item});
            if(this.dragNdrop.where.id == "repairSlot")
            {
               _loc9_ = lol.core.objects.Breakable(this.dragNdrop.what[0].item);
               _loc6_ = _loc9_.getCurQuality();
               _loc8_ = !_loc6_ ? this.cost_mod : this.cost_mod * (1 - _loc6_);
               _loc2_ = this.dragNdrop.what[0].item;
               _loc7_ = _loc2_.getProp("repair_mod");
               if(_loc7_ != null)
               {
                  _loc4_ = Math.floor(_loc8_ * Number(_loc2_.getProp("cost")) * _loc7_);
               }
               else
               {
                  _loc4_ = Math.floor(_loc8_ * Number(_loc2_.getProp("cost")));
               }
               this.repairAfroCost_txt.text = _loc4_;
               this.repairByAfro_btn.enabled = true;
               _loc3_ = _loc2_.getProp("g_cost");
               if(_loc3_)
               {
                  this.restoreGoldCost_txt.text = String(Math.round(_loc3_ * lol.core.GConstatns.gold_restore_price_mod) / 100);
                  this.restoreGold_btn.enabled = true;
               }
               else
               {
                  this.restoreGoldCost_txt.text = "";
                  this.restoreGold_btn.enabled = false;
               }
            }
            else
            {
               this.repairAfroCost_txt.text = "";
               this.repairGoldCost_txt.text = "";
               this.restoreGoldCost_txt.text = "";
               this.repairByAfro_btn.enabled = false;
               this.restoreGold_btn.enabled = false;
            }
         }
         this.dragCont.removeMovieClip();
         delete this.dragNdrop;
         delete this.dragCont.onMouseMove;
      }
   }
   function bagAddItem(obj)
   {
      this.doLater("bagInfo");
      this.repairCostCount();
   }
   function bagRemoveItem(obj)
   {
      this.doLater("bagInfo");
      this.repairCostCount();
   }
   function bagInfo()
   {
      var _loc3_ = new TextFormat();
      _loc3_.bold = true;
      var _loc2_ = this.bag_mc.sortList.length;
      _loc2_ = _loc2_ != undefined ? _loc2_ : 0;
      this.bagInfo_txt.text = _loc2_;
      this.bagInfo_txt.setTextFormat(_loc3_);
   }
   function dragging()
   {
      super.dragging();
      this.bag_mc.startDragAndScroll();
   }
   function _mouseUp(obj)
   {
      super._mouseUp(obj);
      this.bag_mc.stopDragAndScroll();
   }
}
