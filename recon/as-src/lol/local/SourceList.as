class lol.local.SourceList
{
   var _list;
   var _length = 0;
   function SourceList(node, _path)
   {
      this.createList(node,_path);
   }
   function createList(node, _path)
   {
      this._list = new Array();
      var _loc6_ = node.childNodes;
      var _loc3_;
      var _loc2_;
      var _loc4_;
      var _loc5_;
      for(var _loc8_ in _loc6_)
      {
         _loc3_ = _loc6_[_loc8_];
         _loc2_ = _loc3_.attributes.href;
         _loc4_ = _loc3_.attributes.hash;
         if(_loc2_ && _loc4_)
         {
            _loc5_ = new lol.local.SourceObject(_path,_loc2_,_loc4_);
            this._list[_loc2_] = _loc5_;
            this._length = this._length + 1;
         }
      }
   }
   function getList()
   {
      return this._list;
   }
   function getObject(name)
   {
      return this._list[name];
   }
   function get length()
   {
      return this._length;
   }
}
