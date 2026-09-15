class lol.gpui.controls.GPUIList extends lol.gpui.view.ScrollPan
{
   var dispatchEvent;
   var doLater;
   var items_arr;
   var mask_mc;
   var selectedIndex;
   var selectedItem;
   var listItemLink = "listItem";
   var lineSpace = -4;
   var typeOfAlign = 0;
   function GPUIList()
   {
      super();
      this.fillContent();
      this.doLater(this,"init");
      this.items_arr = new Array();
   }
   function init()
   {
      if(this.mask_mc._width > 1)
      {
         this.setSize(this.mask_mc._width,this.mask_mc._height);
      }
   }
   function preSet()
   {
      var _loc3_ = this.mask_mc._width;
      var _loc2_ = this.mask_mc._height;
      this.setSize(_loc3_,_loc2_);
   }
   function setSize(w, h)
   {
      super.setSize(w,h);
   }
   function addItem(obj, withOutStyle)
   {
      var _loc2_ = this.attachItem();
      _loc2_._visible = false;
      _loc2_.label = obj.label;
      _loc2_.data = obj.data;
      _loc2_.addEventListener("release",this,this.click);
      this.items_arr.push(_loc2_);
      this.align();
      this.chekSize();
      var _loc3_ = new lol.utils.Timeout(this,this.checkItem,500,_loc2_,withOutStyle);
      return _loc2_;
   }
   function checkItem(mov, withOutStyle)
   {
      if(!withOutStyle)
      {
         this.itemColor(mov);
      }
      mov.checkPosition();
      mov._visible = true;
   }
   function itemColor(item, color)
   {
      var _loc1_ = lol.gpui.controls.GPUIButton.lavaStyle0;
      var _loc2_ = new lol.utils.Timeout(item,item.setStyle,100,_loc1_);
   }
   function attachItem()
   {
      var _loc2_ = this.content.getNextHighestDepth();
      var _loc3_ = this.content.attachMovie(this.listItemLink,"listItem" + _loc2_,_loc2_);
      return _loc3_;
   }
   function click(obj)
   {
      this.selectItem(obj);
      this.dispatchEvent({type:"click",item:obj.target});
   }
   function selectItem(obj)
   {
      var _loc2_;
      if(obj.target.toggled)
      {
         this.selectedItem = obj.target;
         _loc2_ = 0;
         while(_loc2_ < this.items_arr.length)
         {
            if(this.items_arr[_loc2_] == this.selectedItem)
            {
               this.selectedIndex = _loc2_;
            }
            else
            {
               this.items_arr[_loc2_].toggled = false;
            }
            _loc2_ = _loc2_ + 1;
         }
      }
      else
      {
         this.selectedItem = null;
         this.selectedIndex = null;
      }
      this.dispatchEvent({type:"select",selectedItem:this.selectedItem});
   }
   function quickRemoveItem(i)
   {
      var _loc2_ = this.items_arr[i];
      _loc2_.removeEventListener("click",this);
      this.items_arr.splice(i,1);
      _loc2_.removeMovieClip();
   }
   function removeItem(i)
   {
      this.quickRemoveItem(i);
      this.chekSize();
      this.align();
   }
   function getList()
   {
      return this.items_arr;
   }
   function clearList()
   {
      while(this.items_arr.length > 0)
      {
         this.quickRemoveItem(0);
      }
      this.chekSize();
      this.align();
   }
   function setList(arr)
   {
      var _loc2_ = 0;
      while(_loc2_ < arr.length)
      {
         this.addItem(arr[_loc2_]);
         _loc2_ = _loc2_ + 1;
      }
   }
   function align()
   {
      this.content._y = Math.round(this.content._y);
      var _loc2_ = new lol.utils.Align(this.items_arr);
      if(this.typeOfAlign == 0)
      {
         _loc2_.vAlign(this.lineSpace,0,true);
      }
      else
      {
         _loc2_.vAlign(20,0,false);
      }
      this.boundOY();
   }
}
