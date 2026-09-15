class lol.core.player.Slot
{
   var __classType;
   var __item;
   var __name;
   var __type;
   var dispatchEvent;
   var id;
   function Slot(_id, _type, _classType)
   {
      lol.events.LEventDispatcher.initialize(this);
      this.id = _id;
      this.type = _type;
      this.classType = _classType;
   }
   function addItem(_item)
   {
      if(this.item.id == _item.id)
      {
         return null;
      }
      this.item = _item;
      return this.item;
   }
   function removeItem(_item)
   {
      this.item = null;
   }
   function getItem(id)
   {
      return this.item;
   }
   function set item(_item)
   {
      this.__item = _item;
      this.dispatchEvent({type:"changeSlot"});
   }
   function get item()
   {
      return this.__item;
   }
   function set classType(_ctype)
   {
      this.__classType = _ctype;
   }
   function get classType()
   {
      return this.__classType;
   }
   function set type(_type)
   {
      this.__type = _type;
   }
   function get type()
   {
      return this.__type;
   }
   function set name(_name)
   {
      this.__name = _name;
   }
   function get name()
   {
      return this.__name;
   }
}
