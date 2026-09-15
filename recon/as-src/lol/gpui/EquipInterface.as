class lol.gpui.EquipInterface extends lol.gpui.StaffInterface
{
   var _xmouse;
   var _ymouse;
   var ab0;
   var afroMoneyPan;
   var armor_mc;
   var attachMovie;
   var attribsTitle;
   var bagInfo_txt;
   var bag_mc;
   var belt_mc;
   var bg;
   var boots_mc;
   var cam_mc;
   var changeSkin_btn;
   var clearBag;
   var clearSlot;
   var cost_mod;
   var currDDOperation;
   var ddOperation_arr;
   var deleteItemArr;
   var doLater;
   var dragItemMc;
   var dragSeparate;
   var dragSeparateCancel;
   var dropEnabled;
   var dropTarget;
   var equipment;
   var exchangeMainSize;
   var exchangePanCost_num;
   var exchangePan_cost_mod;
   var exchangePan_showCostInGold;
   var filterPan;
   var getURL;
   var goldMoneyPan;
   var head_mc;
   var initBag;
   var initSlot;
   var legs_mc;
   var listIconPan;
   var myMoneyGold_mc;
   var myMoney_mc;
   var name_txt;
   var onMouseMove;
   var outfitInterface;
   var priceEnabled;
   var prim_mc;
   var sec_mc;
   var separateItem;
   var showItemRepairMod;
   var skillsTitle;
   var slots;
   var sortMask;
   var specTitle;
   var trash_btn;
   var typeOfList;
   var warningDragNdrop;
   var weightPan;
   var showWarningMessage = true;
   var ddFlag = false;
   function EquipInterface()
   {
      super();
      this.doLater("init");
      this.slots = new Array();
      this.slots.bag = this.bag_mc;
      this.slots.primary = this.prim_mc;
      this.slots.secondary = this.sec_mc;
      this.slots.head = this.head_mc;
      this.slots.armor = this.armor_mc;
      this.slots.camouflage = this.cam_mc;
      this.slots.legs = this.legs_mc;
      this.slots.boots = this.boots_mc;
      this.slots.belt = this.belt_mc;
      this.bag_mc.id = "bag";
      this.belt_mc.slotPan_back.useHandCursor = false;
      this.head_mc.slotPan_back.useHandCursor = false;
      this.armor_mc.slotPan_back.useHandCursor = false;
      this.cam_mc.slotPan_back.useHandCursor = false;
      this.legs_mc.slotPan_back.useHandCursor = false;
      this.boots_mc.slotPan_back.useHandCursor = false;
      this.prim_mc.slotPan_back.useHandCursor = false;
      this.sec_mc.slotPan_back.useHandCursor = false;
      this.attribsTitle = new Array();
      this.attribsTitle = ["Сила","Ловкость","Телосложение","Восприятие","Интеллект"];
      this.skillsTitle = new Array();
      this.skillsTitle = ["Ближний бой","Стрельба","Медицина","Промышленность","Производство"];
      this.specTitle = new Array();
      this.specTitle = ["Рукопашный бой","Режущее оружие","Пистолеты","Дробовики","Автоматы","Винтовки","Ручные пулеметы","Пистолет-пулеметы","Хирургия","Первая помощь","Добыча","Переработка","UC1","UC2","UC3"];
   }
   function init()
   {
      var _loc2_ = lol.core.Master.getInstance();
      _loc2_.gamer.requestAttributes();
      this.sortMask = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_MASK_EQUIP);
      this.showWarningMessage = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.WARNING_MESSAGE);
      this.bag_mc.sortMask = this.sortMask;
      this.bag_mc.alignEnabled = true;
      this.bag_mc.addEventListener("changeMask",this,this.changeMaskBag);
      this.bag_mc.addEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.addEventListener("removeItem",this,this.bagRemoveItem);
      this.bag_mc.addEventListener("attaching",this,this.bagAttaching);
      this.filterPan.addEventListener("changeMask",this);
      this.filterPan.init(this.sortMask);
      var _loc3_ = new TextFormat();
      _loc3_.bold = true;
      var _loc4_ = _loc2_.gamer.playerInfo.name;
      this.name_txt.text = _loc4_;
      this.name_txt.setTextFormat(_loc3_);
      this.myMoney_mc.num.text = _loc2_.gamer.attributes.afro;
      this.myMoneyGold_mc.num.text = _loc2_.gamer.attributes.gold;
      this.showMoney(_loc2_.gamer.attributes.afro,_loc2_.gamer.attributes.gold);
      this.equipment = _loc2_.gamer.equipment;
      this.dropTarget = this.equipment;
      this.equipment.addEventListener("addItem",this);
      this.equipment.addEventListener("removeItem",this);
      this.equipment.addEventListener(lol.gpui.DDEvents.TRANSFER_ERROR,this,this.moveItemError);
      this.equipment.addEventListener(lol.gpui.DDEvents.TRANSFER_SUCCESS,this,this.moveItemSuccess);
      this.equipment.addEventListener("separate",this,this.separateAck);
      lol.core.Master.getInstance().gamer.loot.addEventListener(lol.gpui.DDEvents.TRANSFER_ERROR,this,this.moveItemError);
      lol.core.Master.getInstance().gamer.loot.addEventListener(lol.gpui.DDEvents.TRANSFER_SUCCESS,this,this.moveItemSuccess);
      this.trash_btn.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.deleteItem);
      this.trash_btn.hintTitle_str = "Перетащите сюда предмет для его уничтожения";
      this.setSlot(this.bag_mc,"","bag");
      this.outfitInterface.addEventListener(lol.gpui.ItemContainer.SELECT,this,this.select);
      this.outfitInterface.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.outfitInterface.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.outfitInterface.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.outfitInterface.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.outfitInterface.addEventListener(lol.gpui.ItemContainer.RELOAD,this,this._onReload);
      lol.core.SceneShifter.hotKeyManager.addFilter("equipment");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.ESC,this,this.pressEscKey);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.SELECT_ALL,this,this.selectAll);
      this.changeSkin_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showSkinPage);
      this.equipment.firstRequest();
      this.bag_mc.bagPan.setSize(185,336);
      this.listIconPan.addEventListener("changeView",this);
      this.typeOfList = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.TYPE_OF_LIST_EQUIP);
      this.listIconPan.init(this.typeOfList);
      this.bag_mc.typeOfList = this.typeOfList;
      this.initObjects();
      this.weight_info();
      this.outfitInterface.setPlayer(_loc2_.gamer);
   }
   function setSlot(slot_mc, type, name)
   {
      slot_mc.addEventListener(lol.gpui.ItemContainer.SELECT,this,this.select);
      slot_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      slot_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      slot_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      slot_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      slot_mc.addEventListener(lol.gpui.ItemContainer.SEPARATE_HEAP,this,this.separateHeap);
      slot_mc.id = name;
      slot_mc.type = type;
      slot_mc.name = name;
   }
   function cancel()
   {
      lol.core.SceneShifter._sl.closeWinBtn_func();
   }
   function kill()
   {
      this.bag_mc.kill();
      this.outfitInterface.kill();
      this.filterPan.kill();
      this.filterPan.removeEventListener("changeMask",this);
      this.listIconPan.kill();
      this.listIconPan.removeEventListener("changeView",this);
      lol.core.SceneShifter._ref.currentScene.enabledHotKey(true);
      this.equipment.removeEventListener("addItem",this);
      this.equipment.removeEventListener("removeItem",this);
      this.equipment.removeEventListener(lol.gpui.DDEvents.TRANSFER_ERROR,this,this.moveItemError);
      this.equipment.removeEventListener(lol.gpui.DDEvents.TRANSFER_SUCCESS,this,this.moveItemSuccess);
      this.equipment.removeEventListener("separate",this,this.separateAck);
      this.bag_mc.removeEventListener("changeMask",this);
      this.bag_mc.removeEventListener("addItem",this,this.bagAddItem);
      this.bag_mc.removeEventListener("removeItem",this,this.bagRemoveItem);
      this.bag_mc.removeEventListener("attaching",this,this.bagAttaching);
      this.outfitInterface.removeEventListener(lol.gpui.ItemContainer.SELECT,this,this.select);
      this.outfitInterface.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.outfitInterface.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.outfitInterface.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.outfitInterface.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.outfitInterface.removeEventListener(lol.gpui.ItemContainer.RELOAD,this,this._onReload);
      lol.core.SceneShifter.hotKeyManager.removeFilter("equipment");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.ESC,this,this.pressEscKey);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.SELECT_ALL,this,this.selectAll);
      this.trash_btn.removeEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.deleteItem);
      this.changeSkin_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showSkinPage);
      super.kill();
   }
   function startDragNDrop(obj)
   {
      if(!this.ddOperation_arr)
      {
         this.ddOperation_arr = new Array();
      }
      this.ddFlag = true;
      var _loc2_ = obj.item_arr;
      var _loc5_ = obj.target;
      for(var _loc4_ in _loc2_)
      {
         _loc2_[_loc4_].blockItem();
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
      this.currDDOperation.setFrom(_loc2_[0].item,_loc5_,_loc2_[0],_loc2_);
      var _loc3_;
      var _loc6_;
      if(_loc5_ == this.bag_mc && _loc2_.length == 1)
      {
         _loc3_ = this.currDDOperation.fromItem;
         if(_loc3_ instanceof lol.core.objects.Wear)
         {
            _loc6_ = this.getSlot(_loc3_.getProp("slot_type")).id;
            this.outfitInterface.selectSlot(_loc6_);
         }
         else if(_loc3_ instanceof lol.core.objects.FireArm || _loc3_ instanceof lol.core.objects.MeleeWeapon || _loc3_ instanceof lol.core.objects.HealItem || _loc3_ instanceof lol.core.objects.Ammo)
         {
            this.outfitInterface.selectSlot("primary");
            this.outfitInterface.selectSlot("secondary");
         }
      }
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
   function select(obj)
   {
   }
   function doubleClick(obj)
   {
      var _loc2_ = obj.item_mc;
      var _loc4_ = _loc2_.item.getProp("premium");
      var _loc6_;
      var _loc7_;
      if(_loc4_ && _loc4_ > lol.core.Master.getInstance().gamer.premium && this.outfitInterface.prim_mc.id != "bag")
      {
         if(_loc4_ == 1)
         {
            _loc6_ = "У вас должен быть вид на жительство";
         }
         else if(_loc4_ == 2)
         {
            _loc6_ = "У вас должно быть гражданство";
         }
         _loc7_ = lol.core.SceneShifter.openNewWindow("alert");
         _loc7_.content.label = _loc6_;
         return undefined;
      }
      if(!this.ddOperation_arr)
      {
         this.ddOperation_arr = new Array();
      }
      _loc2_.blockItem();
      this.currDDOperation = new lol.gpui.DDOperation();
      this.currDDOperation.setFrom(_loc2_.item,obj.target,_loc2_);
      var _loc3_;
      if(obj.target != this.bag_mc)
      {
         this.currDDOperation.setTo(0,this.bag_mc);
         this.currDDOperation.toItemMc.blockItem();
         this.sendTransferToServer();
      }
      else if(_loc2_.item instanceof lol.core.objects.FireArm || _loc2_.item instanceof lol.core.objects.MeleeWeapon || _loc2_.item instanceof lol.core.objects.Ammo)
      {
         _loc4_ = _loc2_.item.getProp("premium");
         if(_loc4_ && _loc4_ > lol.core.Master.getInstance().gamer.premium && this.currDDOperation.toSlot.id != "bag")
         {
            this.currDDOperation.setTo(this.outfitInterface.prim_mc.item_mc.item,this.outfitInterface.prim_mc,this.outfitInterface.prim_mc.item_mc);
            this.currDDOperation.toItemMc.blockItem();
         }
         this.sendTransferToServer();
      }
      else if(_loc2_.item instanceof lol.core.objects.Wear)
      {
         _loc3_ = this.getSlot(_loc2_.item.getProp("slot_type"));
         this.currDDOperation.setTo(_loc3_.item_mc.item,_loc3_,_loc3_.item_mc);
         this.currDDOperation.toItemMc.blockItem();
         this.sendTransferToServer();
      }
      else if(_loc2_.item instanceof lol.core.objects.HealItem)
      {
         this.equipment.onDoubleClick(this.currDDOperation.fromItem,this.currDDOperation.fromSlot.id);
         _loc2_.unblockItem();
         delete this.currDDOperation;
      }
      else if(_loc2_.item instanceof lol.core.objects.Trash || _loc2_.item instanceof lol.core.objects.Trophy)
      {
         this.currDDOperation.failedOperation();
         delete this.currDDOperation;
      }
      if(!this.currDDOperation.toItem && obj.target == this.bag_mc)
      {
         this.currDDOperation.toSlot.addItem(this.currDDOperation.fromItem);
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
      var _loc3_;
      var _loc4_;
      if(this.ddFlag)
      {
         _loc2_ = obj.target;
         if(_loc2_.id == "bag")
         {
            this.currDDOperation.setTo(0,_loc2_,_loc2_.item_mc);
         }
         else
         {
            _loc3_ = this.currDDOperation.fromItem;
            if(_loc3_ instanceof lol.core.objects.Wear)
            {
               _loc4_ = this.getSlot(_loc3_.getProp("slot_type"));
               this.currDDOperation.setTo(_loc4_.item_mc.item,_loc4_,_loc4_.item_mc);
            }
            else if(_loc3_ instanceof lol.core.objects.FireArm || _loc3_ instanceof lol.core.objects.MeleeWeapon || _loc3_ instanceof lol.core.objects.HealItem || _loc3_ instanceof lol.core.objects.Ammo)
            {
               if(_loc2_.type == "hand")
               {
                  this.currDDOperation.setTo(_loc2_.item_mc.item,_loc2_,_loc2_.item_mc);
               }
               else
               {
                  this.currDDOperation.setTo(this.outfitInterface.prim_mc.item_mc.item,this.outfitInterface.prim_mc,this.outfitInterface.prim_mc.item_mc);
               }
            }
            else
            {
               this.ddFlag = false;
               this.dragItemMc.kill();
               this.dragItemMc.removeMovieClip();
               this.currDDOperation.failedOperation();
               delete this.currDDOperation;
            }
         }
         if(_loc2_.id != "bag" && !this.currDDOperation.group)
         {
            if(!this.currDDOperation.toItem)
            {
               this.currDDOperation.toSlot.addItem(this.currDDOperation.fromItem);
            }
            this.currDDOperation.toItemMc.blockItem();
         }
      }
   }
   function onMouseUp()
   {
      var _loc3_;
      var _loc2_;
      if(this.ddFlag)
      {
         this.ddFlag = false;
         this.dragItemMc.kill();
         this.dragItemMc.removeMovieClip();
         if(this.currDDOperation.heapNum && !this.currDDOperation.group)
         {
            this.sendHeapToServer();
         }
         else if(this._xmouse < 0 || this._xmouse > this.bg._width || this._ymouse < 0 || this._ymouse > this.bg._height)
         {
            if(!this.currDDOperation.group && this.currDDOperation.fromItem instanceof lol.core.objects.Heapable && lol.core.objects.Heapable(this.currDDOperation.fromItem).heapSize > 1)
            {
               this.separateItem = lol.core.objects.Heapable(this.currDDOperation.fromItem);
               _loc3_ = this.createExchangePan(this.separateItem,"Сколько штук выбросить?");
               _loc3_.addEventListener("exchange",this,this.exchangeAck);
               _loc3_.addEventListener("close",this,this.exchangeCancel);
            }
            else
            {
               _loc2_ = lol.core.SceneShifter.openNewWindow("query");
               _loc2_.content.label = "Выкинуть предмет?";
               _loc2_.content.addEventListener("click",this,this.dropItemAck);
            }
         }
         else if(this.trash_btn._xmouse > 0 && this.trash_btn._xmouse < this.trash_btn._width && this.trash_btn._ymouse > 0 && this.trash_btn._ymouse < this.trash_btn._height)
         {
            this.deleteItemArr = this.currDDOperation.fromItemMc_arr;
            this.askDeleteItem();
         }
         else if(!this.currDDOperation.group)
         {
            this.sendTransferToServer();
         }
         else
         {
            this.moveItemError();
         }
      }
      delete this.onMouseMove;
      this.outfitInterface.clearSelect();
   }
   function dropItemAck(obj)
   {
      lol.core.SceneShifter.closeWindow("query");
      obj.target.removeEventListener("click",this,this.dropItemAck);
      var _loc3_;
      var _loc2_;
      if(obj.success)
      {
         _loc3_ = this.currDDOperation.fromItemMc_arr;
         if(_loc3_)
         {
            for(var _loc4_ in _loc3_)
            {
               _loc2_ = new lol.gpui.DDOperation();
               _loc2_.setFrom(_loc3_[_loc4_].item,this.currDDOperation.fromSlot,_loc3_[_loc4_]);
               this.ddOperation_arr.push(_loc2_);
               this.equipment.dropItem(_loc2_.fromItem,_loc2_.fromSlot.id);
            }
         }
         else
         {
            this.ddOperation_arr.push(this.currDDOperation);
            this.equipment.dropItem(this.currDDOperation.fromItem,this.currDDOperation.fromSlot);
         }
         delete this.currDDOperation;
      }
      else
      {
         this.currDDOperation.failedOperation();
      }
   }
   function sendTransferToServer()
   {
      var _loc2_ = this.currDDOperation.fromItem.getProp("premium");
      var _loc3_;
      var _loc4_;
      if(_loc2_ && _loc2_ > lol.core.Master.getInstance().gamer.premium && this.currDDOperation.toSlot.id != "bag")
      {
         if(_loc2_ == 1)
         {
            _loc3_ = "У вас должен быть вид на жительство";
         }
         else if(_loc2_ == 2)
         {
            _loc3_ = "У вас должно быть гражданство";
         }
         _loc4_ = lol.core.SceneShifter.openNewWindow("alert");
         _loc4_.content.label = _loc3_;
         if(!this.currDDOperation.toItem)
         {
            this.currDDOperation.toSlot.removeItem(this.currDDOperation.fromItem);
         }
         this.currDDOperation.failedOperation();
      }
      else if(this.checkForWarning() == "" || this.currDDOperation.toSlot.id == "bag" || !lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.WARNING_MESSAGE))
      {
         this.ddOperation_arr.push(this.currDDOperation);
         this.equipment.transferItem(this.currDDOperation.fromItem,this.currDDOperation.fromSlot.id,this.currDDOperation.toSlot.id,this.currDDOperation.toItem);
         delete this.currDDOperation;
      }
      else
      {
         this.createWarningWindow(this.checkForWarning());
      }
   }
   function sendHeapToServer()
   {
      this.ddOperation_arr.push(this.currDDOperation);
      this.equipment.separateHeap(lol.core.objects.Heapable(this.currDDOperation.fromItem),this.currDDOperation.heapNum);
      delete this.currDDOperation;
   }
   function checkForWarning()
   {
      var _loc4_ = this.currDDOperation.fromItem;
      var _loc3_ = "";
      var _loc2_ = _loc4_.getProp("need_skills");
      _loc3_ += this.checkSkills(_loc2_,this.skillsTitle);
      _loc2_ = _loc4_.getProp("need_attribs");
      _loc3_ += this.checkAttrib(_loc2_,this.attribsTitle);
      _loc2_ = _loc4_.getProp("need_specs");
      _loc3_ += this.checkSpec(_loc2_,this.specTitle);
      return _loc3_;
   }
   function createWarningWindow(warning_str)
   {
      var _loc2_ = lol.core.SceneShifter.openNewWindow("queryWithCheckBox");
      _loc2_.content.addEventListener("click",this,this.warningAnswer);
      _loc2_.content.label = "Не выполняются условия:\r" + warning_str + "Поэтому этот предмет будет ломаться быстрее. Применить?";
      _loc2_.content.checkBoxLabel = "Больше не предупреждать";
   }
   function warningAnswer(obj)
   {
      obj.target.removeEventListener("click",this,this.warningAnswer);
      lol.core.SceneShifter.closeWindow("queryWithCheckBox");
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.WARNING_MESSAGE,!obj.checkBox);
      if(obj.success)
      {
         this.ddOperation_arr.push(this.currDDOperation);
         this.equipment.transferItem(this.currDDOperation.fromItem,this.currDDOperation.fromSlot.id,this.currDDOperation.toSlot.id,this.currDDOperation.toItem);
         delete this.currDDOperation;
      }
      else
      {
         if(!this.currDDOperation.toItem)
         {
            this.currDDOperation.toSlot.removeItem(this.currDDOperation.fromItem);
         }
         this.currDDOperation.failedOperation();
      }
      delete this.warningDragNdrop;
   }
   function moveItemSuccess()
   {
      var _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      _loc2_.successOperation();
   }
   function moveItemError()
   {
      var _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      if(!_loc2_.toItem)
      {
         _loc2_.toSlot.removeItem(_loc2_.fromItem);
      }
      _loc2_.failedOperation();
      this.currDDOperation.fromItemMc.unblockItem();
      this.currDDOperation.failedOperation();
      delete this.currDDOperation;
   }
   function draggingItem()
   {
      this.dragItemMc._x = Math.round(this._xmouse - this.dragItemMc._width / 2);
      this.dragItemMc._y = Math.round(this._ymouse - this.dragItemMc._height / 2);
      if(this._xmouse < 0 || this._xmouse > this.bg._width || this._ymouse < 0 || this._ymouse > this.bg._height)
      {
         if(this.dragItemMc._alpha == 100)
         {
            this.dragItemMc._alpha = 50;
         }
      }
      else if(this.trash_btn._xmouse > 0 && this.trash_btn._xmouse < this.trash_btn._width && this.trash_btn._ymouse > 0 && this.trash_btn._ymouse < this.trash_btn._height)
      {
         if(this.dragItemMc._alpha == 100)
         {
            this.dragItemMc._alpha = 50;
            this.trash_btn.gotoAndStop(2);
         }
      }
      else if(this.dragItemMc._alpha == 50)
      {
         this.dragItemMc._alpha = 100;
         this.trash_btn.gotoAndStop(1);
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
         this.separateItem = lol.core.objects.Heapable(_loc2_);
         _loc4_ = this.createExchangePan(_loc2_);
         _loc4_.addEventListener("exchange",this,this.exchangeAck);
         _loc4_.addEventListener("close",this,this.exchangeCancel);
         this.currDDOperation = new lol.gpui.DDOperation();
         this.currDDOperation.setFrom(_loc2_,obj.target,_loc3_);
      }
   }
   function exchangeAck(obj)
   {
      obj.target.removeEventListener("close",this,this.dragSeparateCancel);
      obj.target.removeEventListener("exchange",this,this.dragSeparate);
      lol.core.SceneShifter.closeWindow("exchange");
      this.currDDOperation.heapNum = obj.left;
      this.sendHeapToServer();
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
   function separateAck(obj)
   {
      var _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      this.equipment.dropItem(_loc2_.fromItem,_loc2_.fromSlot);
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
   function pressEscKey()
   {
      if(this.ddFlag)
      {
         this.ddFlag = false;
         this.dragItemMc.kill();
         this.dragItemMc.removeMovieClip();
         this.currDDOperation.fromItemMc.unblockItem();
         delete this.onMouseMove;
         delete this.currDDOperation;
      }
      else
      {
         this.cancel();
      }
   }
   function deleteItem()
   {
      var _loc2_ = this.bag_mc.selectItem_arr;
      if(_loc2_)
      {
         this.deleteItemArr = _loc2_;
         this.askDeleteItem();
      }
   }
   function askDeleteItem()
   {
      var _loc4_ = false;
      var _loc3_;
      var _loc2_;
      for(var _loc6_ in this.deleteItemArr)
      {
         _loc3_ = this.deleteItemArr[_loc6_].item;
         _loc2_ = _loc3_.getProp("g_cost");
         if(_loc2_)
         {
            _loc4_ = true;
         }
         this.deleteItemArr[_loc6_].blockItem();
      }
      var _loc5_;
      if(_loc4_)
      {
         _loc5_ = lol.core.SceneShifter.openNewWindow("queryDeleteItem");
         _loc5_.content.label = "ВНИМАНИЕ! Восстановление удаленного предмета невозможно. Для подтверждения введите слово \"УДАЛИТЬ\"";
      }
      else
      {
         _loc5_ = lol.core.SceneShifter.openNewWindow("query");
         _loc5_.content.label = this.deleteItemArr.length <= 1 ? "Удалить предмет?" : "Удалить предметы?";
      }
      _loc5_.content.addEventListener("click",this,this.askDeleteItemAck);
      this.trash_btn.gotoAndStop(1);
   }
   function askDeleteItemAck(obj)
   {
      lol.core.SceneShifter.closeWindow("query");
      lol.core.SceneShifter.closeWindow("queryDeleteItem");
      obj.target.removeEventListener("click",this,this.askDeleteItemAck);
      for(var _loc3_ in this.deleteItemArr)
      {
         this.deleteItemArr[_loc3_].unblockItem();
      }
      var _loc2_;
      if(obj.success)
      {
         for(_loc3_ in this.deleteItemArr)
         {
            _loc2_ = new lol.gpui.DDOperation();
            _loc2_.setFrom(this.deleteItemArr[_loc3_].item,this.bag_mc,this.deleteItemArr[_loc3_]);
            this.ddOperation_arr.push(_loc2_);
            this.deleteItemFromServer(this.deleteItemArr[_loc3_]);
         }
      }
      else
      {
         this.currDDOperation.failedOperation();
         delete this.currDDOperation;
         delete this.deleteItemArr;
      }
   }
   function deleteItemFromServer(_itemMc)
   {
      var _loc3_ = lol.core.Master.getInstance().gamer.itemActivator;
      var _loc2_ = new lol.gpui.DDOperation();
      _loc2_.setFrom(_itemMc.item,this.bag_mc,_itemMc);
      this.ddOperation_arr.push(_loc2_);
      lol.core.Master.getInstance().gamer.addEventListener("useAck",this,this.useAck);
      _loc3_.deleteObject(_itemMc.item);
   }
   function useAck(obj)
   {
      var _loc2_;
      if(obj.res)
      {
         _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      }
      else
      {
         _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
         _loc2_.failedOperation();
      }
   }
   function bagAttaching(obj)
   {
      var _loc2_ = obj.proc;
      this.ab0._xscale = _loc2_;
   }
   function showMoney(afro, gold)
   {
      this.afroMoneyPan.value = afro;
      this.goldMoneyPan.type = "gold";
      this.goldMoneyPan.value = gold;
   }
   function initObjects()
   {
      this.initBag(this.equipment.bag);
      this.initSlot("primary");
      this.initSlot("secondary");
      this.initSlot("head");
      this.initSlot("armor");
      this.initSlot("camouflage");
      this.initSlot("legs");
      this.initSlot("boots");
      this.initSlot("belt");
   }
   function clearObjects()
   {
      this.clearBag(this.equipment.bag);
      this.clearSlot("primary");
      this.clearSlot("secondary");
      this.clearSlot("head");
      this.clearSlot("armor");
      this.clearSlot("camouflage");
      this.clearSlot("legs");
      this.clearSlot("boots");
      this.clearSlot("belt");
      this.bag_mc.firstAttaching = true;
   }
   function changeMaskBag(obj)
   {
      this.sortMask = obj.sortMask;
      this.filterPan.sortMaskToggled(this.sortMask);
   }
   function changeMask(obj)
   {
      this.sortMask = obj.sortMask;
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SORT_MASK_EQUIP,this.sortMask);
      this.bag_mc.sortMask = this.sortMask;
      this.bag_mc.resort();
      this.doLater("bagInfo",["bag"]);
   }
   function changeView(obj)
   {
      if(!this.bag_mc.attaching)
      {
         lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.TYPE_OF_LIST_EQUIP,obj.typeOfList);
         this.typeOfList = obj.typeOfList;
         this.bag_mc.linkageItem = obj.linkageItem;
         this.bag_mc.typeOfList = obj.typeOfList;
         this.clearObjects();
         this.doLater("initObjects");
      }
      else
      {
         this.listIconPan._typeOfList();
      }
   }
   function getSlot(str)
   {
      var _loc2_;
      switch(str)
      {
         case 0:
            _loc2_ = this.outfitInterface.head_mc;
            break;
         case 1:
            _loc2_ = this.outfitInterface.cam_mc;
            break;
         case 2:
            _loc2_ = this.outfitInterface.armor_mc;
            break;
         case 3:
            _loc2_ = this.outfitInterface.belt_mc;
            break;
         case 4:
            _loc2_ = this.outfitInterface.legs_mc;
            break;
         case 5:
            _loc2_ = this.outfitInterface.boots_mc;
            break;
         default:
            _loc2_;
      }
      return _loc2_;
   }
   function selectAll()
   {
      this.bag_mc.selectAll();
   }
   function _onReload(obj)
   {
      var _loc5_ = obj.item;
      var _loc2_ = this.attachMovie("reloadContext","reloadContext",2000);
      _loc2_.item = _loc5_;
      var _loc3_ = obj.target.item_mc.reload_btn;
      var _loc7_ = _loc3_._x;
      var _loc6_ = _loc3_._y;
      _loc2_._x = obj.target._x + _loc7_;
      _loc2_._y = obj.target._y + _loc6_;
      _loc2_.showContextMenu(_loc5_);
   }
   function bagAddItem(obj)
   {
      this.doLater("bagInfo");
   }
   function bagRemoveItem(obj)
   {
      this.doLater("bagInfo");
   }
   function addItem(obj)
   {
      super.addItem(obj);
      this.outfitInterface.addItem(obj);
      this.weight_info();
   }
   function removeItem(obj)
   {
      super.removeItem(obj);
      this.outfitInterface.removeItem(obj);
      var _loc3_ = new lol.utils.Timeout(this,this.weight_info,100);
   }
   function bagInfo()
   {
      var _loc2_ = new TextFormat();
      _loc2_.bold = true;
      var _loc3_ = this.bag_mc.sortList.length;
      this.bagInfo_txt.text = _loc3_;
      this.bagInfo_txt.setTextFormat(_loc2_);
   }
   function weight_info()
   {
      this.weightPan.count();
   }
   function checkSkills(arr, titleArr)
   {
      var _loc6_ = "";
      var _loc1_ = 0;
      var _loc4_;
      var _loc5_;
      while(_loc1_ < arr.length)
      {
         _loc4_ = lol.core.Master.getInstance().gamer.attributes.skillArray[_loc1_];
         if(arr[_loc1_] && arr[_loc1_] > _loc4_.level)
         {
            _loc5_ = !titleArr[_loc1_] ? "" : titleArr[_loc1_];
            _loc6_ += "<b>" + titleArr[_loc1_] + " не ниже " + arr[_loc1_] + "</b>\r";
         }
         _loc1_ = _loc1_ + 1;
      }
      return _loc6_;
   }
   function checkAttrib(arr, titleArr)
   {
      var _loc6_ = "";
      var _loc1_ = 0;
      var _loc4_;
      var _loc5_;
      while(_loc1_ < arr.length)
      {
         _loc4_ = lol.core.Master.getInstance().gamer.attributes.attribArray[_loc1_];
         if(arr[_loc1_] && arr[_loc1_] > _loc4_.level)
         {
            _loc5_ = !titleArr[_loc1_] ? "" : titleArr[_loc1_];
            _loc6_ += "<b>" + titleArr[_loc1_] + " не ниже " + arr[_loc1_] + "</b>\r";
         }
         _loc1_ = _loc1_ + 1;
      }
      return _loc6_;
   }
   function checkSpec(arr, titleArr)
   {
      var _loc6_ = "";
      var _loc1_ = 0;
      var _loc3_;
      var _loc5_;
      while(_loc1_ < arr.length)
      {
         _loc3_ = lol.core.Master.getInstance().gamer.attributes.specArray[_loc1_];
         if(arr[_loc1_] && arr[_loc1_] > _loc3_.level)
         {
            _loc5_ = !titleArr[_loc1_] ? "" : titleArr[_loc1_];
            _loc6_ += "<b>" + titleArr[_loc1_] + " не ниже " + arr[_loc1_] + "</b>\r";
         }
         _loc1_ = _loc1_ + 1;
      }
      return _loc6_;
   }
   function showSkinPage()
   {
      var _loc2_ = lol.core.SceneShifter._ref.getProfileUrl();
      this.getURL(_loc2_,"_blank");
   }
}
