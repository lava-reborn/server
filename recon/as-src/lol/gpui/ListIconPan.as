class lol.gpui.ListIconPan extends lol.gpui.GPUIObject
{
   var bagArr;
   var currentType_btn;
   var dispatchEvent;
   var icon_btn;
   var linkageItem;
   var list_btn;
   var typeOfList = "icon";
   var firstLoad = false;
   function ListIconPan()
   {
      super();
      this.doLater("initBtn");
   }
   function initBtn()
   {
      this.icon_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectType);
      this.list_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectType);
      this.icon_btn.hintTitle_str = "Вид с изображением предмета";
      this.list_btn.hintTitle_str = "Вид без изображения предмета";
   }
   function init(_typeOfList)
   {
      this.typeOfList = _typeOfList != undefined ? _typeOfList : this.typeOfList;
      if(this.typeOfList == "icon")
      {
         this.icon_btn.toggled = true;
         this.currentType_btn = this.icon_btn;
      }
      else if(this.typeOfList == "list")
      {
         this.list_btn.toggled = true;
         this.currentType_btn = this.list_btn;
      }
   }
   function kill()
   {
      this.bagArr = null;
      this.icon_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectType);
      this.list_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectType);
   }
   function changeView()
   {
      if(this.typeOfList == "icon")
      {
         this.linkageItem = "extItemCont";
      }
      else if(this.typeOfList == "list")
      {
         this.linkageItem = "extListItemCont";
      }
      this.dispatchEvent({type:"changeView",typeOfList:this.typeOfList,linkageItem:this.linkageItem});
   }
   function selectType(obj)
   {
      var _loc3_ = 0;
      var _loc2_;
      for(var _loc4_ in this.bagArr)
      {
         _loc2_ = this.bagArr[_loc4_].bag_mc.itemStack.length;
         if(_loc2_ > _loc3_)
         {
            _loc3_ = this.bagArr[_loc4_].bag_mc.itemStack.length;
         }
      }
      if(_loc3_ == 0)
      {
         if(this.currentType_btn != obj.target)
         {
            this.currentType_btn.toggled = false;
            this.currentType_btn = obj.target;
            if(this.currentType_btn == this.icon_btn)
            {
               this.typeOfList = "icon";
            }
            else if(this.currentType_btn == this.list_btn)
            {
               this.typeOfList = "list";
            }
            this.changeView();
         }
         else
         {
            this.currentType_btn.toggled = true;
         }
      }
      else
      {
         obj.target.toggled = !obj.target.toggled;
      }
   }
   function _typeOfList()
   {
      if(this.typeOfList == "list")
      {
         this.typeOfList = "icon";
         this.icon_btn.toggled = true;
         this.list_btn.toggled = false;
         this.currentType_btn = this.icon_btn;
      }
      else if(this.typeOfList == "icon")
      {
         this.typeOfList = "list";
         this.list_btn.toggled = true;
         this.icon_btn.toggled = false;
         this.currentType_btn = this.list_btn;
      }
   }
}
