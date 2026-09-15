class lol.gpui.StaffInterface extends lol.gpui.GPUIObject
{
   var _xmouse;
   var _ymouse;
   var annotation;
   var attachMovie;
   var dragCont;
   var dragNdrop;
   var dropTarget;
   var equipment;
   var exchangeMainSize;
   var exchangePanCost_num;
   var exchangePan_cost_mod;
   var exchangePan_showCostInGold;
   var heapSepItem;
   var onMouseMove;
   var priceEnabled;
   var shiftX;
   var shiftY;
   var slots;
   static var ssType;
   var typeOfList = "icon";
   static var SS_TRADE = "trade";
   static var SS_REPAIR = "repair";
   static var SS_BARTER = "barter";
   static var SS_LOOT = "loot";
   static var SS_UPGRADE = "upgrade";
   var cost_mod = 1;
   var dragON = false;
   var dragEnabled = true;
   var dropEnabled = true;
   var showItemRepairMod = false;
   var leftMargin = 45;
   var rightMargin = 45;
   var topMargin = 60;
   var bottomMargin = 20;
   var exchangePanTitle = "";
   function StaffInterface()
   {
      super();
      lol.utils.EMouse.addEventListener(lol.utils.EMouse.DOUBLE_CLICK,this);
   }
   function kill()
   {
      lol.gpui.StaffInterface.ssType = null;
      lol.gpui.AnnotationManager.clear();
      lol.utils.EMouse.removeEventListener(lol.utils.EMouse.DOUBLE_CLICK,this);
   }
   function initBag(target)
   {
      var _loc6_ = target;
      var _loc3_ = _loc6_.getItems();
      var _loc2_ = 0;
      var _loc5_;
      while(_loc2_ < _loc3_.length)
      {
         _loc5_ = _loc3_[_loc2_];
         this.addItem({slot:_loc6_,item:_loc5_});
         _loc2_ = _loc2_ + 1;
      }
   }
   function clearBag(target)
   {
      var _loc6_ = target;
      var _loc3_ = _loc6_.getItems();
      var _loc2_ = 0;
      var _loc5_;
      while(_loc2_ < _loc3_.length)
      {
         _loc5_ = _loc3_[_loc2_];
         this.removeItem({slot:_loc6_,item:_loc5_});
         _loc2_ = _loc2_ + 1;
      }
   }
   function initSlot(sl)
   {
      var _loc2_ = this.equipment[sl];
      var _loc3_ = _loc2_.item;
      if(_loc3_ && _loc2_)
      {
         this.addItem({slot:_loc2_,item:_loc3_});
      }
   }
   function clearSlot(sl)
   {
      var _loc2_ = this.equipment[sl];
      var _loc3_ = _loc2_.item;
      if(_loc3_ && _loc2_)
      {
         this.removeItem({slot:_loc2_,item:_loc3_});
      }
   }
   function addItem(obj)
   {
      var _loc4_ = obj.slot;
      var _loc5_ = obj.item;
      var _loc6_ = obj.i;
      var _loc2_ = this.slots[_loc4_.id];
      _loc2_.addItem(_loc5_,_loc6_);
   }
   function removeItem(obj)
   {
      var _loc3_ = obj.slot;
      var _loc4_ = obj.item;
      var _loc2_ = this.slots[_loc3_.id];
      _loc2_.removeItem(_loc4_);
   }
   function _onPressAnnotation(obj)
   {
      var _loc2_ = obj.item;
      var _loc3_ = obj.target.getFromitemList(_loc2_);
      var _loc6_ = _loc3_.obj.item_mc;
      var _loc4_ = lol.core.SceneShifter.openNewWindow("annotation",undefined,undefined,_loc2_.id);
      this.annotation = _loc4_.content;
      this.annotation.showInfo(_loc2_);
      this.annotation = null;
   }
   function _onMouseOver(obj)
   {
      var _loc5_ = obj.item;
      var _loc6_ = obj.target.getFromitemList(_loc5_);
      var _loc3_ = _loc6_.obj.item_mc;
      this.annotation = lol.gpui.Annotation(this.attachMovie("annotation","annotation",2000));
      var _loc8_ = _loc3_._x != undefined ? _loc3_._x + 178 : 170;
      var _loc4_ = _loc3_._y + obj.target.bagPan.cont_mc._y;
      var _loc7_ = !_loc4_ ? 0 : _loc4_;
      this.annotation._x = obj.target._x + _loc8_ + 2;
      this.annotation._y = obj.target._y + _loc7_;
      this.annotation.showInfo(_loc5_);
   }
   function _onMouseOut(obj)
   {
      this.annotation.removeMovieClip();
   }
   function _mouseDown(obj)
   {
      this.annotation.removeMovieClip();
      this.dragNdrop = new Object();
      this.dragNdrop.from = obj.target;
      var _loc3_;
      if(obj.bag)
      {
         this.dragNdrop.what = obj.item;
      }
      else
      {
         _loc3_ = new Array();
         _loc3_.push(obj);
         this.dragNdrop.what = _loc3_;
      }
      if(obj.target.dragEnabled)
      {
         this.onMouseMove = this.startDrag;
      }
   }
   function startDrag()
   {
      delete this.onMouseMove;
      var _loc2_ = new lol.utils.Timeout(this,this.drag,5);
   }
   function drag()
   {
      var _loc3_;
      if(this.dragEnabled)
      {
         _loc3_ = this.dragNdrop.what.length > 1;
         this.dragON = true;
         if(this.typeOfList == "icon")
         {
            this.dragCont = this.attachMovie("itemCont","dd",10);
            this.dragCont.attachIconEnabled = true;
            this.dragCont.groupItem = _loc3_;
         }
         else if(this.typeOfList == "list")
         {
            this.dragCont = this.attachMovie("listItemCont","dd",10);
            this.dragCont.attachIconEnabled = false;
            this.dragCont.groupItem = _loc3_;
         }
         this.dragCont.priceEnabled = this.priceEnabled;
         this.dragCont.showItemRepairMod = this.showItemRepairMod;
         this.dragCont.cost_mod = this.cost_mod;
         this.dragCont.item = this.dragNdrop.what[0].item;
         this.dragCont.attachIcon(this.dragNdrop.what[0].item);
         this.dragCont.onMouseMove = mx.utils.Delegate.create(this,this.dragging);
         for(var _loc2_ in this.dragNdrop.what)
         {
         }
         this.dragging();
      }
   }
   function shiftBuild()
   {
      var _loc4_ = this.dragNdrop.what[0].item;
      var _loc3_ = this.dragNdrop.from.getFromitemList(_loc4_);
      var _loc2_ = _loc3_.obj.item_mc;
      if(_loc2_)
      {
         this.shiftX = this._xmouse - _loc2_._x - this.dragNdrop.from._x;
         this.shiftY = this._ymouse - _loc2_._y - this.dragNdrop.from._y - this.dragNdrop.from.bagPan.cont_mc._y;
      }
      else
      {
         this.shiftX = this._xmouse - this.dragNdrop.from._x;
         this.shiftY = this._ymouse - this.dragNdrop.from._y;
      }
   }
   function dragging()
   {
      var _loc2_ = -10;
      this.bottomMargin = lol.core.SceneShifter.tempChatShift + 190;
      this.dragCont._x = Math.round(this._xmouse - 0.5 * this.dragCont._width);
      this.dragCont._y = Math.round(this._ymouse - 0.5 * this.dragCont._height);
   }
   function _mouseUp(obj)
   {
      if(this.dropEnabled)
      {
         delete this.onMouseMove;
         this.dragNdrop.where = obj.target;
         if(obj.item && this.dragNdrop.what.length == 1)
         {
            this.dragNdrop.hitted = obj.item;
         }
      }
   }
   function onMouseUp()
   {
      var _loc2_;
      if(this.dropEnabled)
      {
         delete this.onMouseMove;
         this.dragEnabled = true;
         _loc2_ = new lol.utils.Timeout(this,this.drop,1);
      }
   }
   function drop()
   {
      var _loc2_;
      if(this.dragON)
      {
         this.dragNdrop.from.pressOut();
         delete this.dragCont.onMouseMove;
         if(this.checkSeparate())
         {
            _loc2_ = this.proposeSeparate(this.dragNdrop.what[0].item);
            _loc2_.addEventListener("exchange",this,this.dragSeparate);
            _loc2_.addEventListener("close",this,this.dragSeparateCancel);
            if(!_loc2_)
            {
               this.__drop();
            }
         }
         else
         {
            this.__drop();
         }
      }
   }
   function checkSeparate()
   {
      if(this.dragNdrop.what.length == 1 && this.dragNdrop.what[0].item instanceof lol.core.objects.Heapable && this.dragNdrop.from.id != this.dragNdrop.where.id && this.dragNdrop.where.id != undefined)
      {
         return true;
      }
      return false;
   }
   function __drop()
   {
      this.dragON = false;
      for(var _loc2_ in this.dragNdrop.what)
      {
         this.dropTarget.transferItem(this.dragNdrop.what[_loc2_].item,this.dragNdrop.from.id,this.dragNdrop.where.id,this.dragNdrop.hitted);
      }
      this.dragCont.kill();
      this.dragCont.removeMovieClip();
      delete this.dragNdrop;
      delete this.dragCont.onMouseMove;
      this.dragCont.removeMovieClip();
      this.dragON = false;
      this.dragCont = null;
      this.heapSepItem = null;
      this.dropEnabled = true;
   }
   function onDoubleClick()
   {
   }
   function _onDoubleClick()
   {
      delete this.onMouseMove;
      if(!this.dragON && this.dragNdrop.what)
      {
         this.dropTarget.onDoubleClick(this.dragNdrop.what[0].item,this.dragNdrop.from.id);
      }
      this.dragCont.kill();
      this.dragCont.removeMovieClip();
      delete this.dragNdrop;
      delete this.dragCont.onMouseMove;
      this.dragCont.removeMovieClip();
      this.dragON = false;
      this.dragCont = null;
      this.heapSepItem = null;
      this.dropEnabled = true;
   }
   function enableDrag()
   {
      delete this.onMouseMove;
      this.dragON = false;
   }
   function shiftMouseDown(obj)
   {
      if(obj.item instanceof lol.core.objects.Ammo)
      {
         this.dropTarget.separateGroup(obj.item,obj.target.id);
      }
      else if(obj.item instanceof lol.core.objects.FireArm)
      {
      }
   }
   function ctrlMouseDown(obj)
   {
   }
   function proposeSeparate(item)
   {
      var _loc3_;
      var _loc2_;
      if(item instanceof lol.core.objects.Heapable)
      {
         this.heapSepItem = lol.core.objects.Heapable(item);
         if(this.heapSepItem.heapSize > 1)
         {
            _loc3_ = lol.core.SceneShifter.openNewWindow("exchange");
            _loc2_ = _loc3_.content;
            _loc2_.label = this.exchangePanTitle;
            _loc2_.mainSize = this.exchangeMainSize;
            _loc2_.cost_num = this.exchangePanCost_num;
            _loc2_.cost_mod = this.exchangePan_cost_mod;
            _loc2_.showCostInGold = this.exchangePan_showCostInGold;
            _loc2_.maxValue = this.heapSepItem.heapSize;
            this.dropEnabled = false;
            return _loc2_;
         }
      }
   }
   function dragSeparate(obj)
   {
      obj.target.removeEventListener("close",this,this.dragSeparateCancel);
      obj.target.removeEventListener("exchange",this,this.dragSeparate);
      lol.core.SceneShifter.closeWindow("exchange");
      this.dropTarget.separateHeap(this.heapSepItem,obj.left);
      this.dropTarget.addEventListener("separate",this,this.dragSeparateAck);
      this.heapSepItem = null;
   }
   function dragSeparateCancel(obj)
   {
      obj.target.removeEventListener("close",this,this.dragSeparateCancel);
      obj.target.removeEventListener("exchange",this,this.dragSeparate);
      lol.core.SceneShifter.closeWindow("exchange");
      delete this.dragCont.onMouseMove;
      this.dragCont.kill();
      this.dragCont.removeMovieClip();
      this.dragON = false;
      this.dragCont = null;
      this.heapSepItem = null;
      this.dropEnabled = true;
      delete this.dragNdrop;
   }
   function dragSeparateAck(obj)
   {
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
   function handSeparate(obj)
   {
      obj.target.removeEventListener("exchange",this,this.handSeparate);
      obj.target.removeEventListener("close",this,this.handSeparateCancel);
      lol.core.SceneShifter.closeWindow("exchange");
      this.dropTarget.separateHeap(this.heapSepItem,obj.left);
      this.dropTarget.addEventListener("separate",this,this.handSeparateAck);
      this.heapSepItem = null;
      this.dropEnabled = true;
   }
   function handSeparateCancel(obj)
   {
      obj.target.removeEventListener("exchange",this,this.handSeparate);
      obj.target.removeEventListener("close",this,this.handSeparateCancel);
      lol.core.SceneShifter.closeWindow("exchange");
      this.dropEnabled = true;
      delete this.dragNdrop;
   }
   function handSeparateAck(obj)
   {
      obj.target.removeEventListener("separate",this,this.handSeparateAck);
      this.dropEnabled = true;
   }
}
