class lol.gpui.SlotPan extends lol.gpui.GPUIObject
{
   var __name;
   var __type;
   var _height;
   var _width;
   var _xmouse;
   var _ymouse;
   var cont_mc;
   var createEmptyMovieClip;
   var dispatchEvent;
   var item_mc;
   var name_txt;
   var type_txt;
   var linkageItem = "itemCont";
   var typeOfList = "icon";
   var dragEnabled = true;
   function SlotPan()
   {
      super();
      this.cont_mc = this.createEmptyMovieClip("cont_mc",0);
   }
   function addItem(item)
   {
      if(this.typeOfList == "icon")
      {
         this.linkageItem = "itemCont";
      }
      else if(this.typeOfList == "list")
      {
         this.linkageItem = "listItemCont";
      }
      this.item_mc = lol.gpui.ItemContainer(this.cont_mc.attachMovie(this.linkageItem,"slotItem",0));
      this.item_mc.item = item;
      this.item_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.item_mc.addEventListener(lol.gpui.ItemContainer.SELECT,this,this.select);
      this.item_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.item_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.item_mc.addEventListener(lol.gpui.ItemContainer.RELOAD,this,this._onReload);
      if(this.typeOfList == "icon")
      {
         this.item_mc.attachIconEnabled = true;
      }
      else
      {
         this.item_mc.attachIconEnabled = false;
      }
      this.item_mc.attachIcon(item);
      if(item.rootID == lol.core.objects.Item.FIRE_ARM)
      {
         this.item_mc.reload_btn._visible = true;
      }
      this.dispatchEvent({type:"addItem"});
   }
   function removeItem()
   {
      this.item_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.item_mc.removeEventListener(lol.gpui.ItemContainer.SELECT,this,this.select);
      this.item_mc.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.item_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.item_mc.removeEventListener(lol.gpui.ItemContainer.SEPARATE_HEAP,this,this.separateHeap);
      this.item_mc.removeEventListener(lol.gpui.ItemContainer.RELOAD,this,this._onReload);
      this.item_mc.kill();
      this.item_mc.removeMovieClip();
   }
   function startDragNDrop(obj)
   {
      var _loc4_ = obj.target;
      var _loc2_ = new Array();
      _loc2_.push(_loc4_);
      this.dispatchEvent({type:lol.gpui.ItemContainer.START_DRAG_N_DROP,item_mc:_loc4_,item_arr:_loc2_});
   }
   function select(obj)
   {
      var _loc2_ = obj.target;
      this.dispatchEvent({type:lol.gpui.ItemContainer.SELECT,item_mc:_loc2_});
   }
   function doubleClick(obj)
   {
      var _loc2_ = obj.target;
      this.dispatchEvent({type:lol.gpui.ItemContainer.DOUBLE_CLICK,item_mc:_loc2_});
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
   function _mouseDown(obj)
   {
      this.dispatchEvent({type:"_mouseDown",item:obj.target.item});
   }
   function _mouseUp(obj)
   {
      this.dispatchEvent({type:"_mouseUp",item:obj.target.item});
   }
   function onMouseUp()
   {
      var _loc2_ = new flash.geom.Rectangle(0,0,this._width,this._height);
      if(_loc2_.containsPoint(new flash.geom.Point(this._xmouse,this._ymouse)))
      {
         this.dispatchEvent({type:lol.gpui.ItemContainer.DROP});
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
   function _onReload(obj)
   {
      this.dispatchEvent({type:lol.gpui.ItemContainer.RELOAD,item:obj.target.item});
   }
   function get item()
   {
      return this.item_mc.item;
   }
   function set type(_type)
   {
      this.__type = _type;
      this.type_txt.text = _type;
   }
   function get type()
   {
      return this.__type;
   }
   function set name(Name)
   {
      this.__name = Name;
      this.name_txt.text = Name;
   }
   function get name()
   {
      return this.__name;
   }
}
