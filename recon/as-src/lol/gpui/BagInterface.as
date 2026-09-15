class lol.gpui.BagInterface extends lol.gpui.GPUIObject
{
   var _xmouse;
   var _ymouse;
   var bagPan;
   var createEmptyMovieClip;
   var currSelectItem;
   var currentItem_mc;
   var dispatchEvent;
   var dragAndScroll_mc;
   var getNextHighestDepth;
   var handSortMask;
   var hitTest;
   var id;
   var itemList;
   var itemStack;
   var lastClick;
   var onEnterFrame;
   var scrollArea;
   var selectItem_arr;
   var selectList;
   var sortList;
   var sortMask;
   var type = "all";
   var name = "bag";
   var handAlign = false;
   var linkageItem = "extItemCont";
   var typeOfList = "icon";
   var selectAvailable = true;
   var selectGroupAvailable = true;
   var alignEnabled = false;
   var dragEnabled = true;
   var unselectClickOut = true;
   var priceEnabled = false;
   var showHeapCount = true;
   var showPriseInGold = false;
   var dragAndScrollArea = 30;
   var lostFocus = true;
   var showItemRepairMod = false;
   var showItemSellMod = false;
   var cost_mod = 1;
   var totalStackLength = 0;
   var attaching = false;
   var firstAttaching = true;
   var allowClearSelectList = false;
   var unselectFlag = true;
   function BagInterface()
   {
      super();
      this.handSortMask = new Array();
      this.bagPan.scrollValue = 2;
      this.itemList = new Array();
      var _loc3_ = lol.core.Master.getInstance();
      var _loc4_ = _loc3_.gamer.equipment;
      this.scrollArea = new flash.geom.Rectangle(0,0,120,240);
      this.doLater("init");
      this.itemStack = new Array();
   }
   function init()
   {
      this.bagPan.fillContent();
   }
   function kill()
   {
      this.bagPan.kill();
   }
   function addItem(item, pos, n)
   {
      this.itemStack.push({item:item,pos:pos});
      this.totalStackLength = this.itemStack.length;
      this.onEnterFrame = this._addItem;
   }
   function _addItem()
   {
      var _loc2_ = this.itemStack.shift();
      var _loc4_;
      var _loc3_;
      if(_loc2_)
      {
         _loc4_ = _loc2_.item;
         _loc3_ = _loc2_.pos;
         this.__addItem(_loc4_,_loc3_);
      }
      var _loc5_;
      if(this.totalStackLength != 0)
      {
         _loc5_ = Math.round((this.totalStackLength - this.itemStack.length) * 100 / this.totalStackLength);
      }
      this.dispatchEvent({type:"attaching",proc:_loc5_});
      if(this.itemStack.length == 0)
      {
         delete this.onEnterFrame;
         if(this.attaching)
         {
            this.attaching = false;
            this.bagPan.vBar.__position = 0;
            this.bagPan.setPosition(0,0);
         }
         if(this.firstAttaching)
         {
            this.firstAttaching = false;
         }
      }
      else if(!this.attaching)
      {
         this.attaching = true;
      }
   }
   function __addItem(item, pos)
   {
      var _loc5_ = this.bagPan.content;
      var _loc9_ = _loc5_.getNextHighestDepth();
      var _loc6_;
      if(this.typeOfList == "icon")
      {
         _loc6_ = true;
         this.linkageItem = "extItemCont";
      }
      else
      {
         _loc6_ = false;
         this.linkageItem = "extListItemCont";
      }
      var _loc2_ = _loc5_.attachMovie(this.linkageItem,"item" + item.id,_loc9_);
      _loc2_.item = item;
      _loc2_.attachIconEnabled = _loc6_;
      _loc2_.priceEnabled = this.priceEnabled;
      _loc2_.showHeapCount = this.showHeapCount;
      _loc2_.showPriseInGold = this.showPriseInGold;
      _loc2_.cost_mod = this.cost_mod;
      _loc2_.showItemRepairMod = this.showItemRepairMod;
      _loc2_.showItemSellMod = this.showItemSellMod;
      _loc2_.addEventListener(lol.gpui.ItemContainer.SELECT,this,this.select);
      _loc2_.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      _loc2_.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      _loc2_.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      _loc2_.addEventListener(lol.gpui.ItemContainer.SEPARATE_HEAP,this,this.separateHeap);
      _loc2_.addEventListener(lol.gpui.ItemContainer.SHIFT_SELECT,this,this.shiftSelect);
      _loc2_.addEventListener(lol.gpui.ItemContainer.CTRL_SELECT,this,this.ctrlSelect);
      _loc2_.attachIcon(item);
      var _loc3_ = {};
      _loc3_.item_mc = _loc2_;
      _loc3_.item = item;
      _loc3_.classType = item.classType;
      if(pos != undefined && pos < this.itemList.length)
      {
         this.itemList.splice(pos,0,_loc3_);
      }
      else
      {
         this.itemList.push(_loc3_);
      }
      var _loc7_;
      if(!this.firstAttaching)
      {
         _loc7_ = item.rootID;
         this.sortMask[_loc7_] = true;
         this.dispatchEvent({type:"changeMask",sortMask:this.sortMask});
      }
      this.align();
      this.dispatchEvent({type:"addItem",id:this.id});
   }
   function startDragNDrop(obj)
   {
      var _loc3_ = obj.target;
      if(!this.selectItem_arr)
      {
         this.selectItem_arr = new Array();
         this.selectItem_arr.push(_loc3_);
      }
      if(this.dragEnabled)
      {
         this.dispatchEvent({type:lol.gpui.ItemContainer.START_DRAG_N_DROP,item_mc:_loc3_,item_arr:this.selectItem_arr});
      }
      this.clearSelectList();
   }
   function doubleClick(obj)
   {
      var _loc2_ = obj.target;
      this.dispatchEvent({type:lol.gpui.ItemContainer.DOUBLE_CLICK,item_mc:_loc2_});
      this.clearSelectList();
   }
   function mouseUpOnItem(obj)
   {
      var _loc2_ = obj.target;
      this.dispatchEvent({type:lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,item_mc:_loc2_});
   }
   function separateHeap(obj)
   {
      var _loc2_ = obj.target;
      this.dispatchEvent({type:lol.gpui.ItemContainer.SEPARATE_HEAP,item_mc:_loc2_});
   }
   function select(obj)
   {
      var _loc2_ = obj.target;
      this.clearSelectList();
      this.selectItem_arr = new Array();
      this.selectItem_arr.push(_loc2_);
      this.currSelectItem = _loc2_;
      this.currSelectItem.toggled = true;
      this.dispatchEvent({type:lol.gpui.ItemContainer.SELECT,item_mc:_loc2_});
   }
   function shiftSelect(obj)
   {
      var _loc2_ = obj.target;
      if(this.currSelectItem && this.selectGroupAvailable)
      {
         this.itemPressShift(_loc2_);
      }
      else
      {
         this.currSelectItem.toggled = false;
         this.selectItem_arr = new Array();
         this.selectItem_arr.push(_loc2_);
         this.currSelectItem = _loc2_;
         this.currSelectItem.toggled = true;
      }
   }
   function ctrlSelect(obj)
   {
      var _loc2_ = obj.target;
      if(this.selectItem_arr && this.selectGroupAvailable)
      {
         this.currSelectItem = _loc2_;
         this.itemPressCtrl(_loc2_);
      }
      else
      {
         this.currSelectItem.toggled = false;
         this.selectItem_arr = new Array();
         this.selectItem_arr.push(_loc2_);
         this.currSelectItem = _loc2_;
         this.currSelectItem.toggled = true;
      }
   }
   function onMouseUp(obj)
   {
      if(this.hitTest(_root._xmouse,_root._ymouse))
      {
         this.dispatchEvent({type:lol.gpui.ItemContainer.DROP});
      }
      else
      {
         this.dispatchEvent({type:"bagActive",status:false});
         if(this.lostFocus)
         {
            this.clearSelectList();
            this.currSelectItem.toggled = false;
            delete this.currSelectItem;
         }
      }
   }
   function onMouseDown(obj)
   {
      if(this.hitTest(_root._xmouse,_root._ymouse))
      {
         this.dispatchEvent({type:"bagActive",status:true});
      }
   }
   function itemPressShift(item_mc)
   {
      this.clearSelectList();
      var _loc7_;
      var _loc6_;
      var _loc4_;
      var _loc5_;
      var _loc2_;
      var _loc3_;
      if(this.currSelectItem && item_mc != this.currSelectItem)
      {
         this.currSelectItem.toggled = false;
         _loc7_ = this.getNumFromSortList(this.currSelectItem.item.id);
         _loc6_ = this.getNumFromSortList(item_mc.item.id);
         if(_loc6_ > _loc7_)
         {
            _loc4_ = _loc7_;
            _loc5_ = _loc6_;
         }
         else
         {
            _loc4_ = _loc6_;
            _loc5_ = _loc7_;
         }
         this.selectItem_arr = new Array();
         _loc2_ = _loc4_;
         while(_loc2_ <= _loc5_)
         {
            _loc3_ = this.sortList[_loc2_];
            _loc3_.toggled = true;
            this.selectItem_arr.push(_loc3_);
            _loc2_ = _loc2_ + 1;
         }
      }
   }
   function itemPressCtrl(item_mc)
   {
      var _loc2_;
      for(var _loc4_ in this.selectItem_arr)
      {
         if(this.selectItem_arr[_loc4_] == item_mc)
         {
            _loc2_ = Number(_loc4_);
            break;
         }
      }
      if(_loc2_ == undefined)
      {
         item_mc.toggled = true;
         this.selectItem_arr.push(item_mc);
      }
      else
      {
         this.selectItem_arr[_loc2_].toggled = false;
         this.selectItem_arr.splice(_loc2_,1);
      }
   }
   function clearSelectList()
   {
      for(var _loc2_ in this.selectItem_arr)
      {
         this.selectItem_arr[_loc2_].toggled = false;
      }
      delete this.selectItem_arr;
   }
   function getFromitemList(item)
   {
      var _loc3_ = {};
      var _loc2_ = 0;
      while(_loc2_ < this.itemList.length)
      {
         if(this.itemList[_loc2_].item == item)
         {
            _loc3_.obj = this.itemList[_loc2_];
            _loc3_.n = _loc2_;
            return _loc3_;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function getTotalItemWeight()
   {
      var _loc4_ = 0;
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < this.itemList.length)
      {
         _loc3_ = this.itemList[_loc2_].item;
         _loc4_ += _loc3_.getProp("_weight");
         _loc2_ = _loc2_ + 1;
      }
      return _loc4_;
   }
   function removeItem(item)
   {
      var _loc3_ = this.getFromitemList(item);
      var _loc2_ = _loc3_.n;
      if(_loc2_ != undefined)
      {
         this.__removeItem(_loc2_);
      }
   }
   function __removeItem(n)
   {
      var _loc2_ = lol.gpui.ItemContainer(this.itemList[n].item_mc);
      _loc2_.removeEventListener(lol.gpui.ItemContainer.SELECT,this,this.select);
      _loc2_.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      _loc2_.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      _loc2_.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      _loc2_.kill();
      this.itemList.splice(n,1);
      _loc2_.removeMovieClip();
      this.align();
      this.dispatchEvent({type:"removeItem",id:this.id});
   }
   function removeAllItems()
   {
      while(this.itemList.length > 0)
      {
         this.__removeItem(0);
      }
   }
   function _onMouseOver(obj)
   {
      this.dispatchEvent({type:"_onMouseOver",item:obj.target.item});
   }
   function _onMouseOut(obj)
   {
      this.dispatchEvent({type:"_onMouseOut",item:obj.target.item});
   }
   function _onPressAnnotation(obj)
   {
      this.dispatchEvent({type:"_onPressAnnotation",item:obj.target.item});
   }
   function _mouseDown(obj)
   {
      if(this.selectAvailable)
      {
         this.itemPress(obj);
         this.insertInFirstPlace(obj.target.item);
      }
      this.dispatchEvent({type:"_mouseDown",item:this.selectList,bag:true});
   }
   function _mouseUp(obj)
   {
      this.unselectFlag = true;
      this.itemRelease(obj);
      this.dispatchEvent({type:"_mouseUp",item:obj.target.item});
   }
   function shiftMouseDown(obj)
   {
      if(this.selectAvailable && this.selectGroupAvailable)
      {
         this.itemPressShift(obj);
      }
      this.dispatchEvent({type:"shiftMouseDown",item:obj.target.item});
   }
   function ctrlMouseDown(obj)
   {
      if(this.selectAvailable)
      {
         this.ctrlItemPress(obj);
      }
      this.dispatchEvent({type:"ctrlMouseDown",item:obj.target.item});
   }
   function drag(obj)
   {
      this.dispatchEvent({type:"drag",item:obj.target.item});
   }
   function itemPress(obj)
   {
      var _loc3_ = this.isItemInSelectList(obj.target);
      if(!_loc3_)
      {
         if(this.selectList)
         {
            this.clearSelectList();
         }
         this.currentItem_mc.toggled = false;
         this.currentItem_mc = null;
         this.currentItem_mc = obj.target;
         obj.target.toggled = true;
         this.addToSelectList(obj.target);
      }
      this.lastClick = "none";
   }
   function ctrlItemPress(obj)
   {
      var _loc3_;
      if(this.selectGroupAvailable)
      {
         this.currentItem_mc = obj.target;
         _loc3_ = this.addToSelectList(obj.target);
         if(_loc3_)
         {
            obj.target.toggled = true;
         }
         else
         {
            obj.target.toggled = false;
            this.removeFromeSelectList(obj.target);
         }
      }
      this.lastClick = "ctrl";
   }
   function itemRelease(obj)
   {
      if(this.lastClick == "none")
      {
         if(this.selectList)
         {
            this.clearSelectList();
         }
         this.pressOut();
         this.currentItem_mc = obj.target;
         obj.target.toggled = true;
         this.addToSelectList(obj.target);
      }
   }
   function selectAll()
   {
      for(var _loc2_ in this.sortList)
      {
         this.sortList[_loc2_].toggled = true;
         this.addToSelectList(this.sortList[_loc2_]);
      }
   }
   function unselectAll()
   {
      for(var _loc2_ in this.sortList)
      {
         this.sortList[_loc2_].toggled = false;
      }
      this.clearSelectList();
   }
   function isItemInSelectList(mc)
   {
      var _loc2_ = false;
      for(var _loc4_ in this.selectList)
      {
         if(this.selectList[_loc4_].mc == mc)
         {
            _loc2_ = true;
            break;
         }
      }
      return _loc2_;
   }
   function pressOut()
   {
      if(this.selectList)
      {
         this.clearSelectList();
      }
      this.currentItem_mc.toggled = false;
      this.currentItem_mc = null;
   }
   function addToSelectList(mc)
   {
      if(!this.selectList)
      {
         this.selectList = new Array();
      }
      var _loc2_ = false;
      for(var _loc4_ in this.selectList)
      {
         if(this.selectList[_loc4_].mc == mc)
         {
            _loc2_ = true;
            break;
         }
      }
      var _loc5_;
      if(!_loc2_)
      {
         _loc5_ = new Object();
         _loc5_.mc = mc;
         _loc5_.item = mc.item;
         this.selectList.push(_loc5_);
         return true;
      }
      return false;
   }
   function removeFromeSelectList(mc)
   {
      var _loc2_;
      for(var _loc4_ in this.selectList)
      {
         if(this.selectList[_loc4_].mc == mc)
         {
            _loc2_ = Number(_loc4_);
            break;
         }
      }
      this.selectList.splice(_loc2_,1);
   }
   function insertInFirstPlace(item)
   {
      var _loc3_;
      var _loc2_ = 0;
      while(_loc2_ < this.selectList.length)
      {
         if(this.selectList[_loc2_].item.id == item.id)
         {
            _loc3_ = Number(_loc2_);
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
      var _loc5_ = this.selectList[_loc3_];
      this.removeFromeSelectList(_loc5_.mc);
      this.selectList.splice(0,0,_loc5_);
   }
   function getNumFromSortList(id)
   {
      var _loc3_;
      var _loc2_ = 0;
      while(_loc2_ < this.sortList.length)
      {
         if(this.sortList[_loc2_].item.id == id)
         {
            _loc3_ = _loc2_;
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
      return _loc3_;
   }
   function align()
   {
      this.sortDepths();
      var _loc25_;
      var _loc24_;
      var _loc23_;
      if(!this.alignEnabled)
      {
         _loc25_ = this.sortMask[8];
         _loc24_ = this.sortMask[9];
         _loc23_ = this.sortMask[10];
         this.sortMask = [1,1,1,1,1,1,1,1,1,1,1];
         this.sortMask[8] = _loc25_;
         this.sortMask[9] = _loc24_;
         this.sortMask[10] = _loc23_;
      }
      if(this.handAlign)
      {
         this.sortMask = this.handSortMask;
      }
      this.sortList = new Array();
      var _loc11_ = 0;
      var _loc7_;
      var _loc2_;
      var _loc19_;
      var _loc14_;
      var _loc16_;
      var _loc13_;
      var _loc12_;
      var _loc17_;
      var _loc21_;
      var _loc20_;
      var _loc18_;
      var _loc8_;
      var _loc6_;
      var _loc3_;
      var _loc15_;
      var _loc5_;
      var _loc10_;
      var _loc9_;
      var _loc4_;
      for(; _loc11_ < this.itemList.length; _loc11_ = _loc11_ + 1)
      {
         _loc7_ = this.itemList[_loc11_].item;
         _loc2_ = this.itemList[_loc11_].item_mc;
         _loc19_ = _loc7_.rootID;
         _loc14_ = _loc7_.getProp("quest");
         _loc16_ = this.sortMask[_loc19_];
         if(_loc14_ && this.sortMask[7])
         {
            _loc2_._visible = true;
            _loc2_._xscale = _loc2_._xscale = 100;
            this.sortList.push(_loc2_);
         }
         else if(_loc16_ && !_loc14_)
         {
            if(this.sortMask[8])
            {
               _loc13_ = lol.core.Master.getInstance();
               _loc12_ = _loc13_.gamer.attributes;
               _loc17_ = _loc12_.afro;
               _loc21_ = _loc12_.gold;
               _loc20_ = _loc7_.getProp("cost") * this.cost_mod;
               _loc18_ = _loc7_.getProp("g_cost") * this.cost_mod;
               if(_loc20_ > _loc17_ || _loc18_ > _loc21_)
               {
                  _loc2_._visible = false;
                  _loc2_._y = 0;
                  _loc2_._xscale = _loc2_._xscale = 1;
                  continue;
               }
            }
            if(this.sortMask[9])
            {
               _loc13_ = lol.core.Master.getInstance();
               _loc13_.gamer.requestAttributes();
               _loc12_ = _loc13_.gamer.attributes;
               _loc8_ = 0;
               _loc6_ = _loc7_.getProp("need_attribs");
               if(_loc6_ != undefined)
               {
                  _loc3_ = 0;
                  while(_loc3_ < _loc6_.length)
                  {
                     if(_loc6_[_loc3_] != undefined && _loc8_ < _loc6_[_loc3_])
                     {
                        _loc8_ = _loc6_[_loc3_];
                        _loc15_ = _loc3_;
                     }
                     _loc3_ = _loc3_ + 1;
                  }
                  if(_loc8_ > 0)
                  {
                     if(_loc12_.attribArray[_loc15_].level < _loc8_)
                     {
                        _loc2_._visible = false;
                        _loc2_._y = 0;
                        _loc2_._xscale = _loc2_._xscale = 1;
                        continue;
                     }
                  }
               }
               _loc5_ = _loc7_.getProp("need_skills");
               if(_loc5_ != undefined)
               {
                  _loc10_ = 0;
                  _loc3_ = 0;
                  while(_loc3_ < _loc5_.length)
                  {
                     if(_loc5_[_loc3_] != undefined && _loc10_ < _loc5_[_loc3_])
                     {
                        _loc10_ = _loc5_[_loc3_];
                        _loc15_ = _loc3_;
                     }
                     _loc3_ = _loc3_ + 1;
                  }
                  if(_loc10_ > 0)
                  {
                     if(_loc12_.skillArray[_loc15_].level < _loc10_)
                     {
                        _loc2_._visible = false;
                        _loc2_._y = 0;
                        _loc2_._xscale = _loc2_._xscale = 1;
                        continue;
                     }
                  }
               }
               _loc9_ = 0;
               _loc4_ = _loc7_.getProp("need_specs");
               if(_loc4_ != undefined)
               {
                  _loc9_ = 0;
                  _loc3_ = 0;
                  while(_loc3_ < _loc4_.length)
                  {
                     if(_loc4_[_loc3_] != undefined && _loc9_ < _loc4_[_loc3_])
                     {
                        _loc9_ = _loc4_[_loc3_];
                        _loc15_ = _loc3_;
                     }
                     _loc3_ = _loc3_ + 1;
                  }
                  if(_loc9_ > 0)
                  {
                     if(_loc12_.specArray[_loc15_].level < _loc9_)
                     {
                        _loc2_._visible = false;
                        _loc2_._y = 0;
                        _loc2_._xscale = _loc2_._xscale = 1;
                        continue;
                     }
                  }
               }
            }
            _loc2_._visible = true;
            _loc2_._xscale = _loc2_._xscale = 100;
            this.sortList.push(_loc2_);
         }
         else
         {
            _loc2_._visible = false;
            _loc2_._y = 0;
            _loc2_._xscale = _loc2_._xscale = 1;
         }
      }
      var _loc22_ = new lol.utils.Align(this.sortList);
      _loc22_.vAlign(4,0,true);
      var _loc26_ = this.bagPan.content;
      this.dispatchEvent({type:"resort"});
   }
   function resort()
   {
      this.align();
   }
   function startDragAndScroll()
   {
      var _loc3_ = this._xmouse;
      var _loc2_ = this._ymouse;
      if(_loc3_ > 0 && _loc3_ < this.bagPan.maskW && _loc2_ > 0 && _loc2_ < this.bagPan.maskH)
      {
         if(!this.dragAndScroll_mc)
         {
            this.dragAndScroll_mc = this.createEmptyMovieClip("dragAndScroll_mc",this.getNextHighestDepth());
            this.dragAndScroll_mc.onEnterFrame = mx.utils.Delegate.create(this,this.scrolling);
         }
      }
      else
      {
         this.stopDragAndScroll();
      }
   }
   function scrolling()
   {
      var _loc2_ = this._ymouse;
      var _loc3_;
      if(_loc2_ < this.dragAndScrollArea)
      {
         _loc3_ = this.dragAndScrollArea - _loc2_;
         this.bagPan.slideScrollY(_loc3_ * 3);
      }
      else if(_loc2_ > this.bagPan.maskH - this.dragAndScrollArea)
      {
         _loc3_ = this.dragAndScrollArea - (this.bagPan.maskH - _loc2_);
         this.bagPan.slideScrollY((- _loc3_) * 3);
      }
      else
      {
         this.stopDragAndScroll();
      }
   }
   function stopDragAndScroll()
   {
      delete this.dragAndScroll_mc.onEnterFrame;
      this.dragAndScroll_mc.removeMovieClip();
      this.dragAndScroll_mc = null;
   }
   function sortDepths()
   {
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < this.itemList.length)
      {
         _loc3_ = this.itemList[_loc2_].item_mc;
         _loc3_.swapDepths(_loc2_);
         _loc2_ = _loc2_ + 1;
      }
   }
   function getArea()
   {
      return this.scrollArea;
   }
}
